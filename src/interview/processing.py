from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.ingestion.service import ContentIngestionService, ContentQualityError
from src.interview.service import InterviewService


class InterviewProcessingService:
    def __init__(self, session):
        self.session = session
        self.interviews = InterviewsRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self.ingestion = ContentIngestionService(session)
        self.service = InterviewService(session)

    def process_job(self, job) -> dict:
        if job.job_type == "interview_dispatch_invites_v1":
            payload = job.payload_json or {}
            return self.service.dispatch_invites_for_vacancy(
                vacancy_id=payload["vacancy_id"],
                matching_run_id=payload.get("matching_run_id"),
                limit=payload.get("limit", 3),
            )
        if job.job_type == "interview_answer_process_v1":
            return self._process_answer(job)
        raise ValueError(f"Unsupported interview job type: {job.job_type}")

    def _process_answer(self, job) -> dict:
        payload = job.payload_json or {}
        from sqlalchemy import select
        from src.db.models.interviews import InterviewSession

        stmt = select(InterviewSession).where(InterviewSession.id == payload["interview_session_id"])
        session = self.session.execute(stmt).scalar_one_or_none()
        if session is None:
            raise ValueError("Interview session not found.")

        raw_message = self.raw_messages.get_by_id(payload["raw_message_id"])
        if raw_message is None:
            raise ValueError("Interview raw message not found.")

        answer_text = raw_message.text_content
        if not answer_text:
            from src.db.repositories.notifications import NotificationsRepository

            try:
                ingestion_result = self.ingestion.ingest_raw_message(raw_message)
            except ContentQualityError as exc:
                NotificationsRepository(self.session).create(
                    user_id=raw_message.user_id,
                    entity_type="interview_session",
                    entity_id=session.id,
                    template_key="candidate_interview_answer_quality_retry",
                    payload_json={"text": str(exc)},
                )
                return {
                    "status": "quality_retry_required",
                    "interview_session_id": str(session.id),
                    "quality_reason": exc.code,
                }
            except Exception:  # noqa: BLE001
                NotificationsRepository(self.session).create(
                    user_id=raw_message.user_id,
                    entity_type="interview_session",
                    entity_id=session.id,
                    template_key="candidate_interview_answer_text_retry",
                    payload_json={"text": "Voice/video answer saved, but transcription failed. Please resend the answer in text."},
                )
                raise
            answer_text = ingestion_result.text
            self.raw_messages.set_text_content(raw_message, answer_text)

        candidate = type("CandidateRef", (), {"user_id": raw_message.user_id})
        result = self.service._handle_interview_answer_text(
            candidate=candidate,
            session=session,
            raw_message_id=raw_message.id,
            text=answer_text,
            source_content_type=raw_message.content_type,
            file_id=raw_message.file_id,
            store_as_transcript=raw_message.content_type in {"voice", "video"},
        )
        from src.db.repositories.notifications import NotificationsRepository

        NotificationsRepository(self.session).create(
            user_id=raw_message.user_id,
            entity_type="interview_session",
            entity_id=session.id,
            template_key=result.notification_template,
            payload_json={"text": result.notification_text},
        )
        return {"status": result.status, "interview_session_id": str(session.id)}
