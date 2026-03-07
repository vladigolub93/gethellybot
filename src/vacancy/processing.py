from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.ingestion.service import ContentIngestionService
from src.llm.service import (
    safe_detect_vacancy_inconsistencies,
    safe_extract_vacancy_summary,
)
from src.messaging.service import MessagingService
from src.state.service import StateService
from src.vacancy.service import VacancyService
from src.vacancy.states import VACANCY_STATE_CLARIFICATION_QA, VACANCY_STATE_JD_PROCESSING


class VacancyProcessingService:
    def __init__(self, session):
        self.session = session
        self.repo = VacanciesRepository(session)
        self.notifications = NotificationsRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)
        self.vacancy_service = VacancyService(session)
        self.ingestion = ContentIngestionService(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    def process_job(self, job) -> dict:
        if job.job_type == "vacancy_jd_extract_v1":
            return self._process_jd_extract(job)
        if job.job_type == "vacancy_clarification_parse_v1":
            return self._process_clarification_parse(job)
        raise ValueError(f"Unsupported vacancy job type: {job.job_type}")

    def _process_jd_extract(self, job) -> dict:
        payload = job.payload_json or {}
        vacancy = self.repo.get_by_id(payload.get("vacancy_id"))
        version = self.repo.get_version_by_id(payload.get("vacancy_version_id"))
        if vacancy is None or version is None:
            raise ValueError("Vacancy or version was not found for processing.")

        source_text = version.extracted_text or version.transcript_text or ""
        ingestion_mode = "passthrough"
        ingestion_source = version.source_type
        if not source_text:
            try:
                ingestion_result = self.ingestion.ingest_vacancy_version(version)
            except Exception:  # noqa: BLE001
                self.repo.update_version_analysis(
                    version,
                    summary_json={"status": "ingestion_pending", "source_type": version.source_type},
                    normalization_json={"processor": "baseline_vacancy_jd_extract_v1", "ingestion_ready": False},
                    model_name="baseline-ingestion",
                )
                raise
            source_text = ingestion_result.text
            ingestion_mode = ingestion_result.mode
            ingestion_source = ingestion_result.source
            if version.source_type in {"voice_description", "video_description"}:
                self.repo.update_version_source_text(version, transcript_text=source_text)
            else:
                self.repo.update_version_source_text(version, extracted_text=source_text)
            if version.source_raw_message_id is not None:
                raw_message = self.raw_messages.get_by_id(version.source_raw_message_id)
                if raw_message is not None and not raw_message.text_content:
                    self.raw_messages.set_text_content(raw_message, source_text)

        llm_result = safe_extract_vacancy_summary(
            self.session,
            source_text,
            version.source_type,
        )
        summary = llm_result.payload["summary"]
        inconsistency_result = safe_detect_vacancy_inconsistencies(
            self.session,
            source_text=source_text,
            summary=summary,
            fallback_issues=(llm_result.payload.get("inconsistency_json") or {}).get("issues") or [],
        )
        inconsistency_json = inconsistency_result.payload
        self.repo.update_version_analysis(
            version,
            summary_json=summary,
            normalization_json={
                "processor": llm_result.prompt_version,
                "ingestion_ready": True,
                "ingestion_mode": ingestion_mode,
                "ingestion_source": ingestion_source,
                "inconsistency_processor": inconsistency_result.prompt_version,
            },
            inconsistency_json=inconsistency_json,
            prompt_version=f"{llm_result.prompt_version}+{inconsistency_result.prompt_version}",
            model_name=llm_result.model_name,
        )
        self.repo.update_clarifications(
            vacancy,
            role_title=summary.get("role_title"),
            seniority_normalized=summary.get("seniority_normalized"),
            project_description=summary.get("project_description_excerpt"),
            primary_tech_stack_json=summary.get("primary_tech_stack") or [],
        )
        if vacancy.state == VACANCY_STATE_JD_PROCESSING:
            self.state_service.transition(
                entity_type="vacancy",
                entity=vacancy,
                to_state=VACANCY_STATE_CLARIFICATION_QA,
                trigger_type="job",
                trigger_ref_id=job.id,
                metadata_json={"job_type": job.job_type},
            )
        self.notifications.create(
            user_id=vacancy.manager_user_id,
            entity_type="vacancy",
            entity_id=vacancy.id,
            template_key="vacancy_clarification_ready",
            payload_json={
                "text": self._copy(
                    "Vacancy draft is ready. Send budget range, countries allowed, work format, team size, project description, and primary tech stack."
                ),
                "summary": summary,
                "inconsistencies": inconsistency_json,
            },
        )
        return {"status": "clarification_ready", "vacancy_id": str(vacancy.id), "vacancy_version_id": str(version.id)}

    def _process_clarification_parse(self, job) -> dict:
        payload = job.payload_json or {}
        vacancy = self.repo.get_by_id(payload.get("vacancy_id"))
        raw_message = self.raw_messages.get_by_id(payload.get("raw_message_id"))
        if vacancy is None or raw_message is None:
            raise ValueError("Vacancy or raw message was not found for clarification processing.")
        if vacancy.state != VACANCY_STATE_CLARIFICATION_QA:
            return {"status": "ignored", "vacancy_id": str(vacancy.id), "raw_message_id": str(raw_message.id)}
        clarification_text = raw_message.text_content
        if not clarification_text:
            try:
                ingestion_result = self.ingestion.ingest_raw_message(raw_message)
            except Exception:  # noqa: BLE001
                self.notifications.create(
                    user_id=vacancy.manager_user_id,
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                    template_key="vacancy_clarification_text_retry",
                    payload_json={"text": self._copy("Voice/video clarification saved, but transcription failed. Please resend the clarification in text.")},
                )
                raise
            clarification_text = ingestion_result.text
            self.raw_messages.set_text_content(raw_message, clarification_text)

        result = self.vacancy_service.process_clarification_text(
            vacancy=vacancy,
            raw_message_id=raw_message.id,
            text=clarification_text,
            trigger_type="job",
        )
        self.notifications.create(
            user_id=vacancy.manager_user_id,
            entity_type="vacancy",
            entity_id=vacancy.id,
            template_key=result.notification_template,
            payload_json={"text": result.notification_text},
        )
        return {"status": result.status, "vacancy_id": str(vacancy.id), "raw_message_id": str(raw_message.id)}
