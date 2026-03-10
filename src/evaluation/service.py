from dataclasses import dataclass

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.evaluations import EvaluationsRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.users import UsersRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.llm.service import safe_evaluate_candidate
from src.messaging.service import MessagingService
from src.state.service import StateService
from src.telegram.keyboards import manager_review_keyboard
from src.evaluation.package_builder import build_candidate_package


@dataclass(frozen=True)
class ManagerDecisionResult:
    status: str
    notification_template: str
    notification_text: str


class EvaluationService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.verifications = CandidateVerificationsRepository(session)
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
        candidate_user = self.users.get_by_id(candidate.user_id)
        verification = self.verifications.get_latest_submitted_by_profile_id(candidate.id)
        answers = self.interviews.list_answers_for_session(session.id)
        answer_texts = [(answer.answer_text or answer.transcript_text or "") for answer in answers]
        llm_result = safe_evaluate_candidate(
            self.session,
            candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
            vacancy=vacancy,
            answer_texts=answer_texts,
        )
        evaluation = llm_result.payload
        status = "manager_review"
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

        self.state_service.transition(
            entity_type="match",
            entity=match,
            to_state="manager_review",
            trigger_type="job",
            state_field="status",
            metadata_json={
                "evaluation_result_id": str(row.id),
                "recommendation": evaluation.get("recommendation"),
            },
        )
        self.state_service.transition(
            entity_type="candidate_profile",
            entity=candidate,
            to_state="UNDER_MANAGER_REVIEW",
            trigger_type="job",
            metadata_json={
                "evaluation_result_id": str(row.id),
                "recommendation": evaluation.get("recommendation"),
            },
        )
        manager = self.users.get_by_id(vacancy.manager_user_id)
        self.notifications.create(
            user_id=manager.id,
            entity_type="match",
            entity_id=match.id,
            template_key="manager_candidate_review_ready",
            payload_json={
                "text": self._copy(
                    "An interviewed candidate is ready for review. "
                    "I included the interview summary and AI recommendation, and the final decision is yours."
                ),
                "messages": [
                    self._copy("An interviewed candidate is ready for review."),
                    self._copy(
                        "I put the candidate package below, including the interview summary, risks, and recommendation. "
                        "When you're ready, use the buttons to approve or reject."
                    ),
                ],
                "candidate_package": build_candidate_package(
                    candidate_user=candidate_user,
                    candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
                    candidate_profile=candidate,
                    vacancy=vacancy,
                    evaluation=evaluation,
                    verification=verification,
                ),
                "reply_markup": manager_review_keyboard(),
            },
        )

        return {
            "evaluation_result_id": str(row.id),
            "match_id": str(match.id),
            "status": status,
            "final_score": evaluation["final_score"],
        }

    def execute_manager_review_action(self, *, user, raw_message_id, action: str):
        if not user.is_hiring_manager:
            return None

        manager_vacancies = self.vacancies.get_by_manager_user_id(user.id)
        match = self.matches.get_latest_manager_review_for_manager(
            [vacancy.id for vacancy in manager_vacancies]
        )
        if match is None:
            return None

        if action == "approve_candidate":
            return self._approve_candidate(user=user, match=match, raw_message_id=raw_message_id)
        if action == "reject_candidate":
            return self._reject_candidate(user=user, match=match, raw_message_id=raw_message_id)
        return ManagerDecisionResult(
            status="help",
            notification_template="manager_candidate_review_help",
            notification_text=self._copy("Reply 'Approve candidate' or 'Reject candidate'."),
        )

    def _approve_candidate(self, *, user, match, raw_message_id):
        candidate = self.candidates.get_by_id(match.candidate_profile_id)
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        candidate_user = self.users.get_by_id(candidate.user_id)
        manager_user = self.users.get_by_id(user.id)
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
            payload_json={
                "text": self._copy(
                    f"You have been approved for {vacancy.role_title or 'the vacancy'}. "
                    "Here is your hiring manager contact for the next step."
                ),
                "counterparty": self._build_counterparty_payload(manager_user),
            },
        )
        self.notifications.create(
            user_id=user.id,
            entity_type="match",
            entity_id=match.id,
            template_key="manager_candidate_approved",
            payload_json={
                "text": self._copy("Candidate approved. Here is the candidate contact for the next step."),
                "counterparty": self._build_counterparty_payload(candidate_user),
            },
        )
        return ManagerDecisionResult(
            status="approved",
            notification_template="manager_candidate_approved",
            notification_text=self._copy("Candidate approved. Candidate handoff sent."),
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

    @staticmethod
    def _build_counterparty_payload(user) -> dict:
        if user is None:
            return {}
        payload = {
            "name": getattr(user, "display_name", None),
            "username": getattr(user, "username", None),
            "phone_number": getattr(user, "phone_number", None),
        }
        return {key: value for key, value in payload.items() if value}
