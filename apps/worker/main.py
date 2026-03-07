import time

from src.candidate_profile.processing import CandidateProcessingService
from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.session import get_session_factory


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
        processor = CandidateProcessingService(session)
        result = processor.process_job(job)
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
