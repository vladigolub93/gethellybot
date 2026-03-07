from dataclasses import dataclass

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.evaluations import EvaluationsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.users import UsersRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.llm.service import safe_evaluate_candidate
from src.messaging.service import MessagingService
from src.state.service import StateService
from src.shared.text import normalize_command_text
from src.telegram.keyboards import manager_review_keyboard


@dataclass(frozen=True)
class ManagerDecisionResult:
    status: str
    notification_template: str
    notification_text: str


class EvaluationService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matches = MatchingRepository(session)
        self.notifications = NotificationsRepository(session)
        self.evaluations = EvaluationsRepository(session)
        self.users = UsersRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    def evaluate_interview(self, *, interview_session_id) -> dict:
        session = self.interviews.get_by_id(interview_session_id)
        if session is None:
            raise ValueError("Interview session not found.")

        match = self.matches.get_by_id(session.match_id)
        candidate = self.candidates.get_by_id(session.candidate_profile_id)
        candidate_version = self.candidates.get_version_by_id(match.candidate_profile_version_id)
        vacancy = self.vacancies.get_by_id(session.vacancy_id)
        answers = self.interviews.list_answers_for_session(session.id)
        answer_texts = [(answer.answer_text or answer.transcript_text or "") for answer in answers]
        llm_result = safe_evaluate_candidate(
            self.session,
            candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
            vacancy=vacancy,
            answer_texts=answer_texts,
        )
        evaluation = llm_result.payload
        status = "auto_rejected" if evaluation["recommendation"] == "reject" else "manager_review"
        row = self.evaluations.create(
            match_id=match.id,
            interview_session_id=session.id,
            status=status,
            final_score=evaluation["final_score"],
            strengths_json=evaluation["strengths"],
            risks_json=evaluation["risks"],
            recommendation=evaluation["recommendation"],
            report_json=evaluation,
        )

        self.state_service.transition(
            entity_type="interview_session",
            entity=session,
            to_state="EVALUATED",
            trigger_type="job",
            metadata_json={"evaluation_result_id": str(row.id)},
        )

        if status == "auto_rejected":
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state="auto_rejected",
                trigger_type="job",
                state_field="status",
                metadata_json={"evaluation_result_id": str(row.id)},
            )
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=candidate,
                to_state="READY",
                trigger_type="job",
                metadata_json={"reason": "auto_rejected_below_threshold"},
            )
            self.notifications.create(
                user_id=candidate.user_id,
                entity_type="match",
                entity_id=match.id,
                template_key="candidate_auto_rejected",
                payload_json={"text": self._copy("This opportunity did not move forward after evaluation.")},
            )
        else:
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state="manager_review",
                trigger_type="job",
                state_field="status",
                metadata_json={"evaluation_result_id": str(row.id)},
            )
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=candidate,
                to_state="UNDER_MANAGER_REVIEW",
                trigger_type="job",
                metadata_json={"evaluation_result_id": str(row.id)},
            )
            manager = self.users.get_by_id(vacancy.manager_user_id)
            self.notifications.create(
                user_id=manager.id,
                entity_type="match",
                entity_id=match.id,
                template_key="manager_candidate_review_ready",
                payload_json={
                    "text": self._copy("A qualified candidate is ready for review. Use the buttons below to approve or reject."),
                    "candidate_summary": (candidate_version.summary_json or {}) if candidate_version else {},
                    "evaluation": evaluation,
                    "reply_markup": manager_review_keyboard(),
                },
            )

        return {
            "evaluation_result_id": str(row.id),
            "match_id": str(match.id),
            "status": status,
            "final_score": evaluation["final_score"],
        }

    def handle_manager_message(self, *, user, raw_message_id, text: str):
        if not user.is_hiring_manager:
            return None

        manager_vacancies = self.vacancies.get_by_manager_user_id(user.id)
        match = self.matches.get_latest_manager_review_for_manager(
            [vacancy.id for vacancy in manager_vacancies]
        )
        if match is None:
            return None

        lowered = normalize_command_text(text)
        if lowered in {"approve candidate", "approve"}:
            return self._approve_candidate(user=user, match=match, raw_message_id=raw_message_id)
        if lowered in {"reject candidate", "reject"}:
            return self._reject_candidate(user=user, match=match, raw_message_id=raw_message_id)

        return ManagerDecisionResult(
            status="help",
            notification_template="manager_candidate_review_help",
            notification_text=self._copy("Reply 'Approve candidate' or 'Reject candidate'."),
        )

    def _approve_candidate(self, *, user, match, raw_message_id):
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        self.matches.mark_manager_decision(match, status="approved")
        self.state_service.record_transition(
            entity_type="match",
            entity_id=match.id,
            from_state="manager_review",
            to_state="approved",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
        )
        self.state_service.transition(
            entity_type="candidate_profile",
            entity=candidate,
            to_state="APPROVED",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
        )
        self.evaluations.create_introduction_event(
            match_id=match.id,
            candidate_user_id=candidate.user_id,
            manager_user_id=user.id,
            introduction_mode="telegram_handoff",
        )
        self.notifications.create(
            user_id=candidate.user_id,
            entity_type="match",
            entity_id=match.id,
            template_key="candidate_approved_introduction",
            payload_json={"text": self._copy(f"You have been approved for {vacancy.role_title or 'the vacancy'}. Helly will introduce you to the manager.")},
        )
        self.notifications.create(
            user_id=user.id,
            entity_type="match",
            entity_id=match.id,
            template_key="manager_candidate_approved",
            payload_json={"text": self._copy("Candidate approved. Introduction event logged.")},
        )
        return ManagerDecisionResult(
            status="approved",
            notification_template="manager_candidate_approved",
            notification_text=self._copy("Candidate approved. Introduction event logged."),
        )

    def _reject_candidate(self, *, user, match, raw_message_id):
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        self.matches.mark_manager_decision(match, status="rejected")
        self.state_service.record_transition(
            entity_type="match",
            entity_id=match.id,
            from_state="manager_review",
            to_state="rejected",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
        )
        self.state_service.transition(
            entity_type="candidate_profile",
            entity=candidate,
            to_state="REJECTED",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
        )
        self.notifications.create(
            user_id=user.id,
            entity_type="match",
            entity_id=match.id,
            template_key="manager_candidate_rejected",
            payload_json={"text": self._copy("Candidate rejected.")},
        )
        return ManagerDecisionResult(
            status="rejected",
            notification_template="manager_candidate_rejected",
            notification_text=self._copy("Candidate rejected."),
        )
