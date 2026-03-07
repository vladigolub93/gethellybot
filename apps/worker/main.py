import time

from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings


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
            logger.debug("worker_poll_tick")
            time.sleep(settings.worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("worker_stopped")


if __name__ == "__main__":
    main()

