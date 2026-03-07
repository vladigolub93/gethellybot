import time

from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings
from src.db.repositories.files import FilesRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.session import get_session_factory
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage


def dispatch_once() -> dict:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        notifications = NotificationsRepository(session)
        files = FilesRepository(session)
        queue = DatabaseQueueClient(session)

        enqueued_notifications = 0
        for notification in notifications.list_pending_dispatchable(limit=20):
            queue.enqueue(
                JobMessage(
                    job_type="notification_send_telegram_v1",
                    idempotency_key=f"notification:{notification.id}",
                    payload={"notification_id": str(notification.id)},
                    entity_type="notification",
                    entity_id=notification.id,
                )
            )
            notifications.mark_queued(notification)
            enqueued_notifications += 1

        enqueued_files = 0
        for file_row in files.list_pending_storage(limit=20):
            queue.enqueue(
                JobMessage(
                    job_type="file_store_telegram_v1",
                    idempotency_key=f"file:{file_row.id}:store",
                    payload={"file_id": str(file_row.id)},
                    entity_type="file",
                    entity_id=file_row.id,
                )
            )
            files.mark_storage_queued(file_row)
            enqueued_files += 1

        session.commit()
        return {
            "notifications_enqueued": enqueued_notifications,
            "files_enqueued": enqueued_files,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("helly.scheduler")

    logger.info(
        "scheduler_started",
        environment=settings.app_env,
        poll_interval_seconds=settings.scheduler_poll_interval_seconds,
    )

    try:
        while True:
            dispatched = dispatch_once()
            logger.debug("scheduler_tick", **dispatched)
            time.sleep(settings.scheduler_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()
