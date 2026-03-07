import time

from src.config.logging import configure_logging, get_logger
from src.config.settings import get_settings


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
            logger.debug("scheduler_tick")
            time.sleep(settings.scheduler_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()

