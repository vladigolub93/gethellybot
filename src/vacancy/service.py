from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.llm.service import (
    safe_build_deletion_confirmation,
    safe_parse_vacancy_clarifications,
)
from src.messaging.service import MessagingService
from src.state.service import StateService
from src.vacancy.question_prompts import (
    QUESTION_KEYS,
    follow_up_prompt,
    initial_clarification_prompt,
    missing_questions_prompt,
)
from src.vacancy.states import (
    VACANCY_STATE_CLARIFICATION_QA,
    VACANCY_STATE_INTAKE_PENDING,
    VACANCY_STATE_JD_PROCESSING,
    VACANCY_STATE_NEW,
    VACANCY_STATE_OPEN,
)


@dataclass(frozen=True)
class VacancyIntakeResult:
    status: str
    notification_template: str


@dataclass(frozen=True)
class VacancyClarificationResult:
    status: str
    notification_template: str
    notification_text: str


@dataclass(frozen=True)
class VacancyDeletionResult:
    status: str
    notification_template: str
    notification_text: str


class VacancyService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = VacanciesRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matching = MatchingRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)
        self.queue = DatabaseQueueClient(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    def ensure_active_intake_vacancy_for_manager(self, user) -> object:
        vacancy = self.repo.get_latest_incomplete_by_manager_user_id(user.id)
        if vacancy is not None:
            return vacancy

        vacancy = self.repo.create(manager_user_id=user.id, state=VACANCY_STATE_NEW)
        self.state_service.record_transition(
            entity_type="vacancy",
            entity_id=vacancy.id,
            from_state=None,
            to_state=VACANCY_STATE_NEW,
            trigger_type="system",
            actor_user_id=user.id,
            metadata_json={"reason": "vacancy created"},
        )
        return vacancy

    def start_onboarding(self, user, *, trigger_ref_id=None) -> object:
        vacancy = self.ensure_active_intake_vacancy_for_manager(user)
        if vacancy.state == VACANCY_STATE_NEW:
            self.state_service.transition(
                entity_type="vacancy",
                entity=vacancy,
                to_state=VACANCY_STATE_INTAKE_PENDING,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
            )
        return vacancy

    def handle_jd_intake(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text: Optional[str] = None,
        file_id=None,
    ) -> VacancyIntakeResult:
        vacancy = self.ensure_active_intake_vacancy_for_manager(user)
        if vacancy.state == VACANCY_STATE_NEW:
            vacancy = self.start_onboarding(user, trigger_ref_id=raw_message_id)

        if vacancy.state != VACANCY_STATE_INTAKE_PENDING:
            return VacancyIntakeResult(
                status="ignored",
                notification_template="manager_input_not_expected",
            )

        source_type = {
            "text": "pasted_text",
            "document": "document_upload",
            "voice": "voice_description",
            "video": "video_description",
        }.get(content_type, "unsupported")
        if source_type == "unsupported":
            return VacancyIntakeResult(
                status="unsupported",
                notification_template="manager_input_unsupported",
            )

        self.state_service.transition(
            entity_type="vacancy",
            entity=vacancy,
            to_state=VACANCY_STATE_JD_PROCESSING,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={"content_type": content_type},
        )
        version = self.repo.create_version(
            vacancy_id=vacancy.id,
            version_no=self.repo.next_version_no(vacancy.id),
            source_type=source_type,
            source_file_id=file_id,
            source_raw_message_id=raw_message_id,
            extracted_text=text if content_type == "text" else None,
            transcript_text=text if content_type in {"voice", "video"} else None,
        )
        self.repo.set_current_version(vacancy, version.id)
        self.queue.enqueue(
            JobMessage(
                job_type="vacancy_jd_extract_v1",
                payload={
                    "vacancy_id": str(vacancy.id),
                    "vacancy_version_id": str(version.id),
                    "source_type": source_type,
                },
                idempotency_key=f"vacancy_jd_extract_v1:{version.id}",
                entity_type="vacancy_version",
                entity_id=version.id,
            )
        )
        return VacancyIntakeResult(
            status="accepted",
            notification_template="vacancy_jd_received_processing",
        )

    def handle_clarification_answer(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text: Optional[str] = None,
        file_id=None,
    ) -> Optional[VacancyClarificationResult]:
        vacancy = self.ensure_active_intake_vacancy_for_manager(user)
        if vacancy.state != VACANCY_STATE_CLARIFICATION_QA:
            return None

        if content_type == "text":
            return self._apply_clarification_text(
                vacancy=vacancy,
                raw_message_id=raw_message_id,
                text=text,
                actor_user_id=user.id,
                trigger_type="user_action",
            )
        if content_type in {"voice", "video"}:
            self.queue.enqueue(
                JobMessage(
                    job_type="vacancy_clarification_parse_v1",
                    payload={
                        "vacancy_id": str(vacancy.id),
                        "raw_message_id": str(raw_message_id),
                        "file_id": str(file_id) if file_id is not None else None,
                        "content_type": content_type,
                    },
                    idempotency_key=f"vacancy_clarification_parse_v1:{raw_message_id}",
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                )
            )
            return VacancyClarificationResult(
                status="queued",
                notification_template="vacancy_clarification_processing",
                notification_text=self._copy("Clarification answer received. Processing vacancy details."),
            )
        return VacancyClarificationResult(
            status="unsupported",
            notification_template="vacancy_clarification_unsupported",
            notification_text=self._copy("Please answer with text, voice, or video."),
        )

    def process_clarification_text(
        self,
        *,
        vacancy,
        raw_message_id,
        text: Optional[str],
        trigger_type: str,
        actor_user_id=None,
    ) -> VacancyClarificationResult:
        return self._apply_clarification_text(
            vacancy=vacancy,
            raw_message_id=raw_message_id,
            text=text,
            trigger_type=trigger_type,
            actor_user_id=actor_user_id,
        )

    def _apply_clarification_text(
        self,
        *,
        vacancy,
        raw_message_id,
        text: Optional[str],
        trigger_type: str,
        actor_user_id=None,
    ) -> VacancyClarificationResult:
        normalized_text = (text or "").strip()
        if not normalized_text:
            return VacancyClarificationResult(
                status="empty",
                notification_template="vacancy_clarification_help",
                notification_text=initial_clarification_prompt(),
            )

        llm_result = safe_parse_vacancy_clarifications(self.session, normalized_text)
        parsed = llm_result.payload
        if parsed:
            self.repo.update_clarifications(vacancy, **parsed)

        missing_keys = self._missing_clarification_keys(vacancy)
        if not missing_keys:
            self.state_service.transition(
                entity_type="vacancy",
                entity=vacancy,
                to_state=VACANCY_STATE_OPEN,
                trigger_type=trigger_type,
                trigger_ref_id=raw_message_id,
                actor_user_id=actor_user_id,
                metadata_json={"action": "clarifications_completed"},
            )
            self.repo.mark_open(vacancy)
            self.queue.enqueue(
                JobMessage(
                    job_type="matching_run_for_vacancy_v1",
                    payload={
                        "vacancy_id": str(vacancy.id),
                        "trigger_type": "vacancy_open",
                    },
                    idempotency_key=f"matching_run_for_vacancy_v1:{vacancy.id}:vacancy_open",
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                )
            )
            return VacancyClarificationResult(
                status="completed",
                notification_template="vacancy_open",
                notification_text=self._copy("Vacancy is now open and ready for matching."),
            )

        questions_context = self._ensure_questions_context(vacancy)
        question_key = self._next_follow_up_key(questions_context, missing_keys)
        if question_key is not None:
            questions_context["follow_up_used"][question_key] = True
            self.repo.update_questions_context(vacancy, questions_context)
            return VacancyClarificationResult(
                status="follow_up",
                notification_template="vacancy_clarification_follow_up",
                notification_text=follow_up_prompt(question_key),
            )

        return VacancyClarificationResult(
            status="incomplete",
            notification_template="vacancy_clarification_missing",
            notification_text=missing_questions_prompt(missing_keys),
        )

    def _missing_clarification_keys(self, vacancy) -> list[str]:
        missing = []
        if vacancy.budget_min is None and vacancy.budget_max is None:
            missing.append("budget")
        if not vacancy.countries_allowed_json:
            missing.append("countries")
        if not vacancy.work_format:
            missing.append("work_format")
        if vacancy.team_size is None:
            missing.append("team_size")
        if not vacancy.project_description:
            missing.append("project_description")
        if not vacancy.primary_tech_stack_json:
            missing.append("primary_tech_stack")
        return missing

    def _ensure_questions_context(self, vacancy) -> dict:
        current = dict(vacancy.questions_context_json or {})
        follow_up_used = dict(current.get("follow_up_used") or {})
        for key in QUESTION_KEYS:
            follow_up_used.setdefault(key, False)
        current["follow_up_used"] = follow_up_used
        return current

    def _next_follow_up_key(self, questions_context: dict, missing_keys: list[str]) -> Optional[str]:
        follow_up_used = questions_context.get("follow_up_used") or {}
        for key in missing_keys:
            if not follow_up_used.get(key, False):
                return key
        return None

    def handle_deletion_message(
        self,
        *,
        user,
        raw_message_id,
        text: Optional[str],
    ) -> Optional[VacancyDeletionResult]:
        vacancy = self.repo.get_latest_active_by_manager_user_id(user.id)
        if vacancy is None:
            return None

        normalized_text = (text or "").strip().lower()
        deletion_context = self._ensure_deletion_context(vacancy)
        pending = bool(deletion_context.get("pending"))

        if normalized_text in {"cancel delete", "keep vacancy", "don't delete", "dont delete"} and pending:
            deletion_context["pending"] = False
            self._update_deletion_context(vacancy, deletion_context)
            return VacancyDeletionResult(
                status="cancelled",
                notification_template="vacancy_deletion_cancelled",
                notification_text=self._copy("Vacancy deletion cancelled. The vacancy remains active."),
            )

        if normalized_text not in {
            "delete vacancy",
            "delete this vacancy",
            "remove vacancy",
            "confirm delete",
            "confirm delete vacancy",
        }:
            return None

        active_matches = self.matching.list_active_for_vacancy(vacancy.id)
        has_active_interview = any(
            self.interviews.get_active_by_match_id(match.id) is not None for match in active_matches
        )

        if normalized_text in {"confirm delete", "confirm delete vacancy"} and pending:
            return self._execute_deletion(
                vacancy=vacancy,
                raw_message_id=raw_message_id,
                actor_user_id=user.id,
                active_matches=active_matches,
            )

        deletion_context["pending"] = True
        self._update_deletion_context(vacancy, deletion_context)
        confirmation = safe_build_deletion_confirmation(
            self.session,
            entity_type="vacancy",
            has_active_interview=has_active_interview,
            has_active_matches=bool(active_matches),
        )
        return VacancyDeletionResult(
            status="confirmation_required",
            notification_template="vacancy_deletion_confirmation_required",
            notification_text=confirmation.payload["message"],
        )

    def _ensure_deletion_context(self, vacancy) -> dict:
        current = dict(vacancy.questions_context_json or {})
        deletion = dict(current.get("deletion") or {})
        deletion.setdefault("pending", False)
        current["deletion"] = deletion
        return current

    def _update_deletion_context(self, vacancy, context: dict) -> None:
        self.repo.update_questions_context(vacancy, context)

    def _execute_deletion(self, *, vacancy, raw_message_id, actor_user_id, active_matches) -> VacancyDeletionResult:
        deletion_context = self._ensure_deletion_context(vacancy)
        deletion_context["pending"] = False
        self._update_deletion_context(vacancy, deletion_context)

        cancelled_matches = 0
        cancelled_interviews = 0
        for match in active_matches:
            session = self.interviews.get_active_by_match_id(match.id)
            if session is not None:
                self.state_service.transition(
                    entity_type="interview_session",
                    entity=session,
                    to_state="CANCELLED",
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=actor_user_id,
                    metadata_json={"reason": "vacancy_deleted"},
                )
                cancelled_interviews += 1
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state="cancelled",
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=actor_user_id,
                metadata_json={"reason": "vacancy_deleted"},
                state_field="status",
            )
            cancelled_matches += 1

        self.state_service.transition(
            entity_type="vacancy",
            entity=vacancy,
            to_state="DELETED",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=actor_user_id,
            metadata_json={
                "cancelled_matches": cancelled_matches,
                "cancelled_interviews": cancelled_interviews,
            },
        )
        self.repo.soft_delete(vacancy)
        details = []
        if cancelled_matches:
            details.append(f"{cancelled_matches} active match(es)")
        if cancelled_interviews:
            details.append(f"{cancelled_interviews} interview(s)")
        details_text = ""
        if details:
            details_text = " Cancelled: " + ", ".join(details) + "."
        return VacancyDeletionResult(
            status="deleted",
            notification_template="vacancy_deleted",
            notification_text=self._copy(f"Vacancy deleted and removed from active flow.{details_text}"),
        )
