from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.core import RawMessage


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
        )
        self.session.add(raw_message)
        self.session.flush()
        return raw_message

    def attach_file(self, raw_message: RawMessage, file_id: UUID) -> RawMessage:
        raw_message.file_id = file_id
        self.session.flush()
        return raw_message

    def set_text_content(self, raw_message: RawMessage, text_content: Optional[str]) -> RawMessage:
        raw_message.text_content = text_content
        self.session.flush()
        return raw_message
