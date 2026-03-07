from __future__ import annotations

from src.db.repositories.files import FilesRepository
from src.integrations.supabase_storage import SupabaseStorageClient
from src.integrations.telegram_bot import TelegramBotClient


class FileStorageService:
    def __init__(self, session):
        self.session = session
        self.files = FilesRepository(session)
        self.telegram = TelegramBotClient()
        self.storage = SupabaseStorageClient()

    def process_job(self, job) -> dict:
        if job.job_type != "file_store_telegram_v1":
            raise ValueError(f"Unsupported file job type: {job.job_type}")

        payload = job.payload_json or {}
        file_row = self.files.get_by_id(payload["file_id"])
        if file_row is None:
            raise ValueError("File was not found.")
        if file_row.storage_key and file_row.status == "stored":
            return {
                "status": "already_stored",
                "file_id": str(file_row.id),
                "storage_key": file_row.storage_key,
            }
        try:
            if not file_row.telegram_file_id:
                raise ValueError("Telegram file_id is not available for storage sync.")

            file_info = self.telegram.get_file(telegram_file_id=file_row.telegram_file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                raise ValueError("Telegram file_path is missing.")

            content = self.telegram.download_file_bytes(file_path=file_path)
            self.storage.ensure_bucket()

            extension = file_row.extension or "bin"
            owner_prefix = str(file_row.owner_user_id) if file_row.owner_user_id else "unowned"
            storage_key = f"telegram/{owner_prefix}/{file_row.id}.{extension}"
            upload_result = self.storage.upload_bytes(
                storage_key=storage_key,
                content=content,
                content_type=file_row.mime_type,
            )
            self.files.mark_stored(
                file_row,
                storage_key=storage_key,
                provider_metadata={
                    "telegram_file_path": file_path,
                    "supabase_upload": upload_result,
                },
            )
            return {
                "status": "stored",
                "file_id": str(file_row.id),
                "storage_key": storage_key,
            }
        except Exception as exc:
            self.files.mark_storage_failed(file_row, error_message=str(exc))
            raise
