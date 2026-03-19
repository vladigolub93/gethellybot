from typing import List, Optional
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from src.db.models.core import Notification, RawMessage


class RawMessagesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_update_id(self, telegram_update_id: int) -> Optional[RawMessage]:
        stmt = select(RawMessage).where(RawMessage.telegram_update_id == telegram_update_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, raw_message_id: UUID) -> Optional[RawMessage]:
        stmt = select(RawMessage).where(RawMessage.id == raw_message_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        user_id: Optional[UUID],
        telegram_update_id: Optional[int],
        telegram_message_id: Optional[int],
        telegram_chat_id: Optional[int],
        direction: str,
        content_type: str,
        payload_json: dict,
        text_content: Optional[str],
        file_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
    ) -> RawMessage:
        raw_message = RawMessage(
            user_id=user_id,
            telegram_update_id=telegram_update_id,
            telegram_message_id=telegram_message_id,
            telegram_chat_id=telegram_chat_id,
            direction=direction,
            content_type=content_type,
            payload_json=payload_json,
            text_content=text_content,
            file_id=file_id,
            correlation_id=correlation_id,
        )
        self.session.add(raw_message)
        self.session.flush()
        return raw_message

    def list_outbound_by_correlation(self, *, correlation_id: UUID) -> List[RawMessage]:
        stmt = (
            select(RawMessage)
            .where(
                RawMessage.direction == "outbound",
                RawMessage.correlation_id == correlation_id,
            )
            .order_by(RawMessage.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars())

    def has_outbound_for_correlation(self, *, correlation_id: UUID) -> bool:
        stmt = select(
            exists().where(
                RawMessage.direction == "outbound",
                RawMessage.correlation_id == correlation_id,
            )
        )
        return bool(self.session.execute(stmt).scalar())

    def get_latest_reply_anchor_message_id(
        self,
        *,
        user_id,
        match_id,
        template_keys: List[str],
        telegram_chat_id: Optional[int] = None,
    ) -> Optional[int]:
        if not template_keys:
            return None
        stmt = (
            select(RawMessage.telegram_message_id)
            .join(Notification, Notification.id == RawMessage.correlation_id)
            .where(
                RawMessage.direction == "outbound",
                RawMessage.user_id == user_id,
                RawMessage.telegram_message_id.is_not(None),
                Notification.user_id == user_id,
                Notification.template_key.in_(template_keys),
                Notification.payload_json["match_id"].astext == str(match_id),
            )
            .order_by(Notification.created_at.desc(), RawMessage.created_at.desc())
            .limit(1)
        )
        if telegram_chat_id is not None:
            stmt = stmt.where(RawMessage.telegram_chat_id == telegram_chat_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def attach_file(self, raw_message: RawMessage, file_id: UUID) -> RawMessage:
        raw_message.file_id = file_id
        self.session.flush()
        return raw_message

    def set_text_content(self, raw_message: RawMessage, text_content: Optional[str]) -> RawMessage:
        raw_message.text_content = text_content
        self.session.flush()
        return raw_message

    def list_recent_text_context(self, *, user_id: UUID, limit: int = 6) -> List[str]:
        stmt = (
            select(RawMessage)
            .where(
                RawMessage.user_id == user_id,
                RawMessage.text_content.is_not(None),
            )
            .order_by(RawMessage.created_at.desc())
            .limit(limit)
        )
        rows = list(self.session.execute(stmt).scalars())
        rendered: List[str] = []
        for row in reversed(rows):
            text = (row.text_content or "").strip()
            if not text:
                continue
            speaker = "User" if row.direction == "inbound" else "Helly"
            rendered.append(f"{speaker}: {text}")
        return rendered
