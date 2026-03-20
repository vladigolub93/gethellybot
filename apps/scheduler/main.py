import time
from collections import Counter
from typing import Optional

from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings
from src.db.repositories.files import FilesRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.notifications import NotificationsRepository
from src.db.session import get_session_factory
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.monitoring.telegram_alerts import TelegramErrorAlertService


def dispatch_once(*, batch_limit: Optional[int] = None) -> dict:
    settings = get_settings()
    limit = int(batch_limit or settings.scheduler_dispatch_batch_size)
    session_factory = get_session_factory()
    session = session_factory()
    try:
        notifications = NotificationsRepository(session)
        files = FilesRepository(session)
        matching = MatchingRepository(session)
        queue = DatabaseQueueClient(session)

        enqueued_notifications = 0
        for notification in notifications.list_pending_dispatchable(limit=limit):
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
        for file_row in files.list_pending_storage(limit=limit):
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

        enqueued_wave_evaluations = 0
        enqueued_wave_reminders = 0
        for wave in matching.list_due_invite_wave_reminders(limit=limit):
            queue.enqueue(
                JobMessage(
                    job_type="matching_send_invite_wave_reminder_v1",
                    idempotency_key=f"matching_send_invite_wave_reminder_v1:{wave.id}",
                    payload={"invite_wave_id": str(wave.id)},
                    entity_type="invite_wave",
                    entity_id=wave.id,
                )
            )
            enqueued_wave_reminders += 1

        for wave in matching.list_due_invite_wave_evaluations(limit=limit):
            queue.enqueue(
                JobMessage(
                    job_type="matching_evaluate_invite_wave_v1",
                    idempotency_key=f"matching_evaluate_invite_wave_v1:{wave.id}",
                    payload={"invite_wave_id": str(wave.id)},
                    entity_type="invite_wave",
                    entity_id=wave.id,
                )
            )
            enqueued_wave_evaluations += 1

        session.commit()
        return {
            "notifications_enqueued": enqueued_notifications,
            "files_enqueued": enqueued_files,
            "invite_wave_reminders_enqueued": enqueued_wave_reminders,
            "invite_wave_evaluations_enqueued": enqueued_wave_evaluations,
        }
    except Exception as exc:
        session.rollback()
        TelegramErrorAlertService().send_error_alert(
            source="scheduler_dispatch_once",
            summary="Scheduler dispatch cycle failed.",
            exc=exc,
        )
        raise
    finally:
        session.close()


def dispatch_until_idle(*, batch_limit: int, max_cycles: int) -> dict:
    totals: Counter[str] = Counter()
    cycles = 0
    while cycles < max_cycles:
        dispatched = dispatch_once(batch_limit=batch_limit)
        cycles += 1
        totals.update(dispatched)
        if sum(dispatched.values()) == 0:
            break
    payload = dict(totals)
    payload["cycles"] = cycles
    return payload


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("helly.scheduler")

    logger.info(
        "scheduler_started",
        environment=settings.app_env,
        poll_interval_seconds=settings.scheduler_poll_interval_seconds,
        dispatch_batch_size=settings.scheduler_dispatch_batch_size,
        max_cycles_per_tick=settings.scheduler_max_cycles_per_tick,
    )

    try:
        while True:
            dispatched = dispatch_until_idle(
                batch_limit=settings.scheduler_dispatch_batch_size,
                max_cycles=settings.scheduler_max_cycles_per_tick,
            )
            logger.debug("scheduler_tick", **dispatched)
            dispatched_total = sum(
                value for key, value in dispatched.items() if key != "cycles"
            )
            if dispatched_total == 0:
                time.sleep(settings.scheduler_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()
