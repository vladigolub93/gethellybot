import time

from src.candidate_profile.processing import CandidateProcessingService
from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.session import get_session_factory
from src.evaluation.service import EvaluationService
from src.interview.processing import InterviewProcessingService
from src.matching.processing import MatchingProcessingService
from src.notifications.delivery import NotificationDeliveryService
from src.storage.service import FileStorageService
from src.vacancy.processing import VacancyProcessingService


def _process_job(session, job):
    if job.job_type.startswith("candidate_"):
        return CandidateProcessingService(session).process_job(job)
    if job.job_type.startswith("evaluation_"):
        payload = job.payload_json or {}
        return EvaluationService(session).evaluate_interview(
            interview_session_id=payload["interview_session_id"],
        )
    if job.job_type.startswith("interview_"):
        return InterviewProcessingService(session).process_job(job)
    if job.job_type.startswith("matching_"):
        return MatchingProcessingService(session).process_job(job)
    if job.job_type.startswith("notification_"):
        return NotificationDeliveryService(session).process_job(job)
    if job.job_type.startswith("file_"):
        return FileStorageService(session).process_job(job)
    if job.job_type.startswith("vacancy_"):
        return VacancyProcessingService(session).process_job(job)
    raise ValueError(f"Unsupported job type: {job.job_type}")


def process_once() -> bool:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        repo = JobExecutionLogsRepository(session)
        job = repo.claim_next_queued()
        if job is None:
            session.commit()
            return False

        repo.mark_started(job)
        result = _process_job(session, job)
        repo.mark_completed(job, result_json=result)
        session.commit()
        return True
    except Exception as exc:
        session.rollback()

        if "job" in locals() and job is not None:
            session = session_factory()
            try:
                repo = JobExecutionLogsRepository(session)
                failed_job = repo.get_by_id(job.id)
                if failed_job is not None:
                    repo.mark_failed(failed_job, error_message=str(exc))
                    session.commit()
            finally:
                session.close()

        raise
    finally:
        session.close()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("helly.worker")

    logger.info(
        "worker_started",
        environment=settings.app_env,
        queue_backend=settings.queue_backend,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )

    try:
        while True:
            try:
                processed = process_once()
                logger.debug("worker_poll_tick", processed_job=processed)
            except Exception as exc:
                logger.exception("worker_poll_failed", error=str(exc))
            time.sleep(settings.worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("worker_stopped")


if __name__ == "__main__":
    main()
