from src.telegram.normalizer import normalize_telegram_update


class TelegramProcessingService:
    def __init__(self, session):
        self.session = session

    def process_job(self, job) -> dict:
        if job.job_type != "telegram_update_process_v1":
            raise ValueError(f"Unsupported telegram job type: {job.job_type}")

        payload = job.payload_json or {}
        update = payload.get("update")
        if not isinstance(update, dict):
            raise ValueError("Telegram update payload is missing.")

        normalized_update = normalize_telegram_update(update)
        from src.telegram.service import TelegramUpdateService

        result = TelegramUpdateService(self.session).process(normalized_update)
        return {
            "status": result.status,
            "deduplicated": result.deduplicated,
            "user_id": result.user_id,
        }
