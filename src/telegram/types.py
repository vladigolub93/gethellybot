from dataclasses import dataclass
from typing import Optional


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
    payload: dict

