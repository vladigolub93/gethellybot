from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.core import File


class FilesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, file_id) -> Optional[File]:
        stmt = select(File).where(File.id == file_id)
        return self.session.execute(stmt).scalar_one_or_none()

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

    def list_pending_storage(self, *, limit: int = 20) -> list[File]:
        stmt = (
            select(File)
            .where(
                File.source == "telegram",
                File.status == "received",
                File.telegram_file_id.is_not(None),
            )
            .order_by(File.created_at.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def mark_storage_queued(self, file_row: File) -> File:
        file_row.status = "storage_queued"
        self.session.flush()
        return file_row

    def mark_stored(
        self,
        file_row: File,
        *,
        storage_key: str,
        provider_metadata: Optional[dict] = None,
    ) -> File:
        file_row.status = "stored"
        file_row.storage_key = storage_key
        if provider_metadata:
            current_metadata = dict(file_row.provider_metadata or {})
            current_metadata.update(provider_metadata)
            file_row.provider_metadata = current_metadata
        self.session.flush()
        return file_row

    def mark_storage_failed(self, file_row: File, *, error_message: str) -> File:
        file_row.status = "storage_failed"
        current_metadata = dict(file_row.provider_metadata or {})
        current_metadata["storage_error"] = error_message[:1000]
        file_row.provider_metadata = current_metadata
        self.session.flush()
        return file_row

    def mark_deleted(self, file_row: File, *, reason: str) -> File:
        file_row.status = "deleted"
        file_row.deleted_at = datetime.now(timezone.utc)
        current_metadata = dict(file_row.provider_metadata or {})
        current_metadata["cleanup_reason"] = reason[:1000]
        file_row.provider_metadata = current_metadata
        self.session.flush()
        return file_row
