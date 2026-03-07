from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.core import File


class FilesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_telegram_unique_file_id(self, telegram_unique_file_id: str) -> Optional[File]:
        stmt = select(File).where(File.telegram_unique_file_id == telegram_unique_file_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create_or_get_from_telegram(
        self,
        *,
        owner_user_id,
        kind: str,
        telegram_file_id: str,
        telegram_unique_file_id: Optional[str],
        mime_type: Optional[str],
        extension: Optional[str],
        size_bytes: Optional[int],
        provider_metadata: Optional[dict],
    ) -> File:
        if telegram_unique_file_id:
            existing = self.get_by_telegram_unique_file_id(telegram_unique_file_id)
            if existing is not None:
                existing.owner_user_id = owner_user_id or existing.owner_user_id
                existing.telegram_file_id = telegram_file_id or existing.telegram_file_id
                existing.mime_type = mime_type or existing.mime_type
                existing.extension = extension or existing.extension
                existing.size_bytes = size_bytes or existing.size_bytes
                existing.provider_metadata = provider_metadata or existing.provider_metadata
                self.session.flush()
                return existing

        file_row = File(
            owner_user_id=owner_user_id,
            source="telegram",
            kind=kind,
            telegram_file_id=telegram_file_id,
            telegram_unique_file_id=telegram_unique_file_id,
            mime_type=mime_type,
            extension=extension,
            size_bytes=size_bytes,
            provider_metadata=provider_metadata,
            status="received",
        )
        self.session.add(file_row)
        self.session.flush()
        return file_row
