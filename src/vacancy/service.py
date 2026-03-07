from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.db.repositories.vacancies import VacanciesRepository
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.state.service import StateService
from src.vacancy.question_parser import parse_vacancy_clarifications
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


class VacancyService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = VacanciesRepository(session)
        self.state_service = StateService(session)
        self.queue = DatabaseQueueClient(session)

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
                notification_text="Clarification answer received. Processing vacancy details.",
            )
        return VacancyClarificationResult(
            status="unsupported",
            notification_template="vacancy_clarification_unsupported",
            notification_text="Please answer with text, voice, or video.",
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

        parsed = parse_vacancy_clarifications(normalized_text)
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
                notification_text="Vacancy is now open and ready for matching.",
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
