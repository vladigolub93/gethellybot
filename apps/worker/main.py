import time

from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.session import get_session_factory
from src.jobs.processor import process_job
from src.monitoring.telegram_alerts import TelegramErrorAlertService


def process_once() -> bool:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        repo = JobExecutionLogsRepository(session)
        job = repo.claim_next_queued_prefer_non_notification()
        if job is None:
            session.commit()
            return False

        repo.mark_started(job)
        result = process_job(session, job)
        repo.mark_completed(job, result_json=result)
        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        alert_context = {}

        if "job" in locals() and job is not None:
            alert_context = {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "entity_type": job.entity_type,
                "entity_id": str(job.entity_id) if job.entity_id else None,
            }
            session = session_factory()
            try:
                repo = JobExecutionLogsRepository(session)
                failed_job = repo.get_by_id(job.id)
                if failed_job is not None:
                    repo.mark_failed(failed_job, error_message=str(exc))
                    session.commit()
            finally:
                session.close()

        TelegramErrorAlertService().send_error_alert(
            source="worker_process_once",
            summary="Worker job processing failed.",
            exc=exc,
            context=alert_context,
        )
        raise
    finally:
        session.close()


def process_batch(*, max_jobs: int) -> int:
    processed_jobs = 0
    while processed_jobs < max_jobs:
        processed = process_once()
        if not processed:
            break
        processed_jobs += 1
    return processed_jobs


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("helly.worker")

    logger.info(
        "worker_started",
        environment=settings.app_env,
        queue_backend=settings.queue_backend,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        worker_concurrency=settings.worker_concurrency,
        max_jobs_per_tick=settings.worker_max_jobs_per_tick,
    )

    try:
        while True:
            try:
                processed_jobs = process_batch(max_jobs=settings.worker_max_jobs_per_tick)
                logger.debug("worker_poll_tick", processed_jobs=processed_jobs)
            except Exception as exc:
                logger.exception("worker_poll_failed", error=str(exc))
                processed_jobs = 0
            if processed_jobs == 0:
                time.sleep(settings.worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("worker_stopped")


if __name__ == "__main__":
    main()
