from src.candidate_profile.states import (
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_SUMMARY_REVIEW,
)
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.candidate_profile.service import CandidateProfileService
from src.ingestion.service import ContentIngestionService
from src.llm.service import safe_extract_candidate_summary, safe_merge_candidate_summary
from src.state.service import StateService


class CandidateProcessingService:
    def __init__(self, session):
        self.session = session
        self.repo = CandidateProfilesRepository(session)
        self.notifications = NotificationsRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self.state_service = StateService(session)
        self.candidate_service = CandidateProfileService(session)
        self.ingestion = ContentIngestionService(session)

    def process_job(self, job) -> dict:
        if job.job_type == "candidate_cv_extract_v1":
            return self._process_cv_extract(job)
        if job.job_type == "candidate_summary_edit_apply_v1":
            return self._process_summary_edit(job)
        if job.job_type == "candidate_questions_parse_v1":
            return self._process_questions_parse(job)
        raise ValueError(f"Unsupported job type: {job.job_type}")

    def _process_cv_extract(self, job) -> dict:
        payload = job.payload_json or {}
        profile = self.repo.get_by_id(payload.get("candidate_profile_id"))
        version = self.repo.get_version_by_id(payload.get("candidate_profile_version_id"))
        if profile is None or version is None:
            raise ValueError("Candidate profile or version was not found for processing.")

        source_text = version.extracted_text or version.transcript_text or ""
        ingestion_mode = "passthrough"
        ingestion_source = version.source_type
        if not source_text:
            try:
                ingestion_result = self.ingestion.ingest_candidate_version(version)
            except Exception:  # noqa: BLE001
                self.repo.update_version_analysis(
                    version,
                    summary_json={
                        "status": "ingestion_pending",
                        "source_type": version.source_type,
                    },
                    normalization_json={
                        "processor": "baseline_cv_extract_v1",
                        "ingestion_ready": False,
                    },
                    approval_status="ingestion_pending",
                    model_name="baseline-ingestion",
                )
                raise
            source_text = ingestion_result.text
            ingestion_mode = ingestion_result.mode
            ingestion_source = ingestion_result.source
            if version.source_type == "voice_description":
                self.repo.update_version_source_text(version, transcript_text=source_text)
            else:
                self.repo.update_version_source_text(version, extracted_text=source_text)
            if version.source_raw_message_id is not None:
                raw_message = self.raw_messages.get_by_id(version.source_raw_message_id)
                if raw_message is not None and not raw_message.text_content:
                    self.raw_messages.set_text_content(raw_message, source_text)

        llm_result = safe_extract_candidate_summary(
            self.session,
            source_text,
            version.source_type,
        )
        summary = llm_result.payload
        self.repo.update_version_analysis(
            version,
            summary_json=summary,
            normalization_json={
                "processor": llm_result.prompt_version,
                "ingestion_ready": True,
                "ingestion_mode": ingestion_mode,
                "ingestion_source": ingestion_source,
            },
            approval_status="pending_user_review",
            model_name=llm_result.model_name,
            prompt_version=llm_result.prompt_version,
        )
        if profile.state != CANDIDATE_STATE_SUMMARY_REVIEW:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_SUMMARY_REVIEW,
                trigger_type="job",
                trigger_ref_id=job.id,
                metadata_json={"job_type": job.job_type},
            )
        self.notifications.create(
            user_id=profile.user_id,
            entity_type="candidate_profile",
            entity_id=profile.id,
            template_key="candidate_summary_ready_for_review",
            payload_json={
                "text": "Your profile summary is ready. Reply 'Approve summary' or 'Edit summary: ...'.",
                "summary": summary,
            },
        )
        return {
            "status": "summary_ready",
            "candidate_profile_id": str(profile.id),
            "candidate_profile_version_id": str(version.id),
        }

    def _process_summary_edit(self, job) -> dict:
        payload = job.payload_json or {}
        profile = self.repo.get_by_id(payload.get("candidate_profile_id"))
        version = self.repo.get_version_by_id(payload.get("candidate_profile_version_id"))
        base_version = self.repo.get_version_by_id(payload.get("base_version_id"))
        if profile is None or version is None or base_version is None:
            raise ValueError("Candidate profile or summary version was not found for edit processing.")

        llm_result = safe_merge_candidate_summary(
            self.session,
            dict(base_version.summary_json or {}),
            payload.get("edit_request_text") or "",
        )
        merged_summary = llm_result.payload
        self.repo.update_version_analysis(
            version,
            summary_json=merged_summary,
            normalization_json={
                "processor": llm_result.prompt_version,
                "base_version_id": str(base_version.id),
            },
            approval_status="pending_user_review",
            model_name=llm_result.model_name,
            prompt_version=llm_result.prompt_version,
        )
        if profile.state == CANDIDATE_STATE_CV_PROCESSING:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_SUMMARY_REVIEW,
                trigger_type="job",
                trigger_ref_id=job.id,
                metadata_json={"job_type": job.job_type},
            )
        self.notifications.create(
            user_id=profile.user_id,
            entity_type="candidate_profile",
            entity_id=profile.id,
            template_key="candidate_summary_ready_for_review",
            payload_json={
                "text": "Updated summary is ready. Reply 'Approve summary' or 'Edit summary: ...'.",
                "summary": merged_summary,
            },
        )
        return {
            "status": "summary_ready",
            "candidate_profile_id": str(profile.id),
            "candidate_profile_version_id": str(version.id),
            "edited": True,
        }

    def _process_questions_parse(self, job) -> dict:
        payload = job.payload_json or {}
        profile = self.repo.get_by_id(payload.get("candidate_profile_id"))
        raw_message = self.raw_messages.get_by_id(payload.get("raw_message_id"))
        if profile is None or raw_message is None:
            raise ValueError("Candidate profile or raw message was not found for question processing.")
        if profile.state != CANDIDATE_STATE_QUESTIONS_PENDING:
            return {
                "status": "ignored",
                "candidate_profile_id": str(profile.id),
                "raw_message_id": str(raw_message.id),
            }

        question_text = raw_message.text_content
        if not question_text:
            try:
                ingestion_result = self.ingestion.ingest_raw_message(raw_message)
            except Exception:  # noqa: BLE001
                self.notifications.create(
                    user_id=profile.user_id,
                    entity_type="candidate_profile",
                    entity_id=profile.id,
                    template_key="candidate_questions_text_retry",
                    payload_json={
                        "text": "Voice/video answer saved, but transcription failed. Please send salary, location, and work format in text.",
                    },
                )
                raise
            question_text = ingestion_result.text
            self.raw_messages.set_text_content(raw_message, question_text)

        result = self.candidate_service.process_question_answer_text(
            profile=profile,
            raw_message_id=raw_message.id,
            text=question_text,
            trigger_type="job",
        )
        self.notifications.create(
            user_id=profile.user_id,
            entity_type="candidate_profile",
            entity_id=profile.id,
            template_key=result.notification_template,
            payload_json={"text": result.notification_text},
        )
        return {
            "status": result.status,
            "candidate_profile_id": str(profile.id),
            "raw_message_id": str(raw_message.id),
        }
