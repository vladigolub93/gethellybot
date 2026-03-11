from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NormalizedTelegramFile:
    kind: str
    telegram_file_id: str
    telegram_unique_file_id: Optional[str]
    file_name: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    extension: Optional[str]
    payload: dict


@dataclass(frozen=True)
class NormalizedTelegramUpdate:
    update_id: int
    telegram_user_id: int
    telegram_chat_id: int
    message_id: Optional[int]
    content_type: str
    text: Optional[str]
    contact_phone_number: Optional[str]
    display_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]
    file: Optional[NormalizedTelegramFile]
    payload: dict
    chat_type: Optional[str] = None
    chat_title: Optional[str] = None
    callback_query_id: Optional[str] = None
    callback_data: Optional[str] = None
