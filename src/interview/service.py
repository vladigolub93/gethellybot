from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.interview.question_plan import build_question_plan
from src.interview.states import (
    INTERVIEW_SESSION_ACCEPTED,
    INTERVIEW_SESSION_COMPLETED,
    INTERVIEW_SESSION_CREATED,
    INTERVIEW_SESSION_IN_PROGRESS,
)
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.llm.service import (
    safe_build_interview_question_plan,
    safe_conduct_interview_turn,
    safe_decide_interview_followup,
    safe_parse_interview_answer,
)
from src.messaging.service import MessagingService
from src.state.service import StateService


@dataclass(frozen=True)
class InterviewUserResult:
    status: str
    notification_template: str
    notification_text: str


class InterviewService:
    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.matches = MatchingRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.interviews = InterviewsRepository(session)
        self.notifications = NotificationsRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)
        self.queue = DatabaseQueueClient(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    @staticmethod
    def _question_prompt_text(question) -> str:
        return question.question_text

    @staticmethod
    def _vacancy_context(vacancy) -> dict:
        return {
            "role_title": getattr(vacancy, "role_title", None),
            "seniority_normalized": getattr(vacancy, "seniority_normalized", None),
            "primary_tech_stack_json": getattr(vacancy, "primary_tech_stack_json", None),
            "project_description": getattr(vacancy, "project_description", None),
            "work_format": getattr(vacancy, "work_format", None),
        }

    @staticmethod
    def _question_payload(question, *, question_id: Optional[int] = None) -> dict:
        if question is None:
            return {}
        return {
            "id": question_id,
            "type": question.question_kind if question.question_kind != "follow_up" else None,
            "question": question.question_text,
        }

    def _render_interview_utterance(
        self,
        *,
        mode: str,
        candidate_summary: dict,
        vacancy,
        session,
        current_question,
        candidate_answer: str | None = None,
        answer_quality: str | None = None,
        follow_up_used: bool = False,
        follow_up_reason: str | None = None,
        candidate_first_name: str | None = None,
    ) -> str:
        conductor = safe_conduct_interview_turn(
            self.session,
            mode=mode,
            candidate_first_name=candidate_first_name,
            candidate_summary=candidate_summary,
            vacancy_context=self._vacancy_context(vacancy),
            interview_plan=(session.plan_json or {}).get("questions") or [],
            current_question=self._question_payload(current_question, question_id=session.current_question_order),
            candidate_answer=candidate_answer,
            answer_quality=answer_quality,
            follow_up_used=follow_up_used,
            follow_up_reason=follow_up_reason,
        )
        return conductor.payload.get("utterance") or self._question_prompt_text(current_question)

    def dispatch_invites_for_vacancy(self, *, vacancy_id, limit: int = 3) -> dict:
        vacancy = self.vacancies.get_by_id(vacancy_id)
        matches = self.matches.list_shortlisted_for_vacancy(vacancy_id, limit=limit)
        invited_count = 0
        for match in matches:
            candidate = self.candidates.get_by_id(match.candidate_profile_id)
            if candidate is None:
                continue
            self.matches.mark_invited(match)
            self.state_service.record_transition(
                entity_type="match",
                entity_id=match.id,
                from_state="shortlisted",
                to_state="invited",
                trigger_type="job",
                metadata_json={"vacancy_id": str(vacancy_id)},
            )
            self.notifications.create(
                user_id=candidate.user_id,
                entity_type="match",
                entity_id=match.id,
                template_key="candidate_interview_invitation",
                payload_json={
                    "text": self.messaging.compose_interview_invitation(
                        role_title=getattr(vacancy, "role_title", None)
                    ),
                },
            )
            invited_count += 1
        return {"vacancy_id": str(vacancy_id), "invited_count": invited_count}

    def handle_candidate_message(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text=None,
        file_id=None,
    ):
        candidate = self.candidates.get_active_by_user_id(user.id)
        if candidate is None:
            return None

        active_session = self.interviews.get_active_session_for_candidate(candidate.id)
        if active_session is not None:
            return self._handle_interview_answer(
                candidate=candidate,
                session=active_session,
                raw_message_id=raw_message_id,
                content_type=content_type,
                text=text,
                file_id=file_id,
            )

        invited_match = self.matches.get_latest_invited_for_candidate(candidate.id)
        if invited_match is None:
            return None

        lowered = (text or "").strip().lower()
        if content_type == "text" and lowered in {"accept interview", "accept"}:
            return self._accept_invitation(
                candidate=candidate,
                match=invited_match,
                raw_message_id=raw_message_id,
            )
        if content_type == "text" and lowered in {"skip opportunity", "skip"}:
            self.matches.mark_candidate_responded(invited_match, status="skipped")
            self.state_service.record_transition(
                entity_type="match",
                entity_id=invited_match.id,
                from_state="invited",
                to_state="skipped",
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=user.id,
            )
            return InterviewUserResult(
                status="skipped",
                notification_template="candidate_interview_skipped",
                notification_text=self._copy("Opportunity skipped."),
            )

        return InterviewUserResult(
            status="invite_pending",
            notification_template="candidate_interview_invitation_help",
            notification_text=self._copy("Reply 'Accept interview' or 'Skip opportunity'."),
        )

    def _accept_invitation(self, *, candidate, match, raw_message_id):
        self.matches.mark_candidate_responded(match, status="accepted")
        self.state_service.record_transition(
            entity_type="match",
            entity_id=match.id,
            from_state="invited",
            to_state="accepted",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=candidate.user_id,
        )

        session = self.interviews.get_session_by_match_id(match.id)
        vacancy = self.vacancies.get_by_id(match.vacancy_id)
        candidate_version = self.candidates.get_version_by_id(match.candidate_profile_version_id)
        if session is None:
            llm_result = safe_build_interview_question_plan(
                self.session,
                vacancy=vacancy,
                candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
            )
            plan = llm_result.payload["questions"] or build_question_plan(
                vacancy=vacancy,
                candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
            )
            session = self.interviews.create_session(
                match_id=match.id,
                candidate_profile_id=match.candidate_profile_id,
                vacancy_id=match.vacancy_id,
                state=INTERVIEW_SESSION_CREATED,
                plan_json={"questions": plan},
            )
            self.state_service.record_transition(
                entity_type="interview_session",
                entity_id=session.id,
                from_state=None,
                to_state=INTERVIEW_SESSION_CREATED,
                trigger_type="system",
                metadata_json={"match_id": str(match.id)},
            )
            for order_no, plan_item in enumerate(plan, start=1):
                if isinstance(plan_item, dict):
                    question_text = plan_item.get("question")
                    question_kind = plan_item.get("type") or "primary"
                else:
                    question_text = str(plan_item)
                    question_kind = "primary"
                self.interviews.create_question(
                    session_id=session.id,
                    order_no=order_no,
                    question_text=question_text,
                    question_kind=question_kind,
                )
            self.interviews.set_total_questions(session, len(plan))

        self.state_service.transition(
            entity_type="interview_session",
            entity=session,
            to_state=INTERVIEW_SESSION_ACCEPTED,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=candidate.user_id,
        )
        self.interviews.mark_accepted(session)

        self.state_service.transition(
            entity_type="interview_session",
            entity=session,
            to_state=INTERVIEW_SESSION_IN_PROGRESS,
            trigger_type="system",
            trigger_ref_id=raw_message_id,
            actor_user_id=candidate.user_id,
        )
        self.interviews.mark_started(session)
        first_question = self.interviews.get_question_by_order(session.id, session.current_question_order)
        if first_question is not None and first_question.asked_at is None:
            self.interviews.mark_question_asked(first_question)
        opening_text = self._render_interview_utterance(
            mode="opening",
            candidate_summary=(candidate_version.summary_json or {}) if candidate_version else {},
            vacancy=vacancy,
            session=session,
            current_question=first_question,
        )

        return InterviewUserResult(
            status="accepted",
            notification_template="candidate_interview_started",
            notification_text=opening_text if first_question is not None else "Interview started.",
        )

    def _handle_interview_answer(
        self,
        *,
        candidate,
        session,
        raw_message_id,
        content_type: str,
        text=None,
        file_id=None,
    ):
        if content_type == "text":
            return self._handle_interview_answer_text(
                candidate=candidate,
                session=session,
                raw_message_id=raw_message_id,
                text=text,
            )

        if content_type in {"voice", "video"}:
            self.queue.enqueue(
                JobMessage(
                    job_type="interview_answer_process_v1",
                    payload={
                        "interview_session_id": str(session.id),
                        "raw_message_id": str(raw_message_id),
                        "file_id": str(file_id) if file_id is not None else None,
                        "content_type": content_type,
                    },
                    idempotency_key=f"interview_answer_process_v1:{raw_message_id}",
                    entity_type="interview_session",
                    entity_id=session.id,
                )
            )
            return InterviewUserResult(
                status="queued",
                notification_template="candidate_interview_answer_processing",
                notification_text=self._copy("Answer received. Processing it now."),
            )

        return InterviewUserResult(
            status="unsupported",
            notification_template="candidate_interview_answer_unsupported",
            notification_text=self._copy("Please answer with text, voice, or video."),
        )

    def _handle_interview_answer_text(self, *, candidate, session, raw_message_id, text):
        question = self.interviews.get_question_by_order(session.id, session.current_question_order)
        if question is None:
            return InterviewUserResult(
                status="missing_question",
                notification_template="candidate_interview_state_error",
                notification_text=self._copy("Interview state is inconsistent. Please try again."),
            )

        self.interviews.create_answer(
            session_id=session.id,
            question_id=question.id,
            raw_message_id=raw_message_id,
            content_type="text",
            answer_text=text,
            is_follow_up_answer=question.question_kind == "follow_up",
        )
        self.interviews.mark_question_answered(question)

        match = self.matches.get_by_id(session.match_id)
        candidate_version = (
            self.candidates.get_version_by_id(match.candidate_profile_version_id)
            if match is not None
            else None
        )
        vacancy = self.vacancies.get_by_id(session.vacancy_id)
        candidate_summary = (candidate_version.summary_json or {}) if candidate_version else {}
        answer_parse = safe_parse_interview_answer(
            self.session,
            question_text=question.question_text,
            candidate_answer=text or "",
            candidate_summary=candidate_summary,
        )
        followup_decision = safe_decide_interview_followup(
            self.session,
            question_text=question.question_text,
            question_kind=question.question_kind,
            candidate_answer=text or "",
            candidate_summary=candidate_summary,
            vacancy_context=self._vacancy_context(vacancy),
            follow_up_already_used=question.question_kind == "follow_up",
            answer_parse=answer_parse.payload,
        )

        if (
            question.question_kind != "follow_up"
            and followup_decision.payload.get("ask_followup")
            and followup_decision.payload.get("followup_question")
        ):
            next_order = session.current_question_order + 1
            self.interviews.shift_questions_from_order(session.id, next_order)
            followup = self.interviews.create_question(
                session_id=session.id,
                order_no=next_order,
                question_text=followup_decision.payload["followup_question"],
                question_kind="follow_up",
                parent_question_id=question.id,
            )
            self.interviews.set_total_questions(session, session.total_questions + 1)
            self.interviews.advance_question_pointer(session, next_order)
            self.interviews.mark_question_asked(followup)
            followup_text = self._render_interview_utterance(
                mode="ask_follow_up",
                candidate_summary=candidate_summary,
                vacancy=vacancy,
                session=session,
                current_question=followup,
                candidate_answer=text or "",
                answer_quality=followup_decision.payload.get("answer_quality"),
                follow_up_used=True,
                follow_up_reason=followup_decision.payload.get("followup_reason"),
            )
            return InterviewUserResult(
                status="follow_up_question",
                notification_template="candidate_interview_follow_up_question",
                notification_text=followup_text,
            )

        if session.current_question_order >= session.total_questions:
            self.state_service.transition(
                entity_type="interview_session",
                entity=session,
                to_state=INTERVIEW_SESSION_COMPLETED,
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=candidate.user_id,
            )
            self.interviews.mark_completed(session)
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state="interview_completed",
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=candidate.user_id,
                state_field="status",
            )
            self.queue.enqueue(
                JobMessage(
                    job_type="evaluation_score_interview_v1",
                    payload={
                        "interview_session_id": str(session.id),
                        "match_id": str(match.id),
                    },
                    idempotency_key=f"evaluation_score_interview_v1:{session.id}",
                    entity_type="interview_session",
                    entity_id=session.id,
                )
            )
            closing_text = self._render_interview_utterance(
                mode="closing",
                candidate_summary=candidate_summary,
                vacancy=vacancy,
                session=session,
                current_question=question,
                candidate_answer=text or "",
                answer_quality=followup_decision.payload.get("answer_quality"),
                follow_up_used=question.question_kind == "follow_up",
                follow_up_reason=followup_decision.payload.get("followup_reason"),
            )
            return InterviewUserResult(
                status="completed",
                notification_template="candidate_interview_completed",
                notification_text=closing_text,
            )

        next_order = session.current_question_order + 1
        self.interviews.advance_question_pointer(session, next_order)
        next_question = self.interviews.get_question_by_order(session.id, next_order)
        if next_question is not None and next_question.asked_at is None:
            self.interviews.mark_question_asked(next_question)
        next_question_text = self._render_interview_utterance(
            mode="move_to_next_question",
            candidate_summary=candidate_summary,
            vacancy=vacancy,
            session=session,
            current_question=next_question,
            candidate_answer=text or "",
            answer_quality=followup_decision.payload.get("answer_quality"),
            follow_up_used=question.question_kind == "follow_up",
            follow_up_reason=followup_decision.payload.get("followup_reason"),
        )
        return InterviewUserResult(
            status="next_question",
            notification_template="candidate_interview_next_question",
            notification_text=next_question_text if next_question is not None else "Next question is ready.",
        )
