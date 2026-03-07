from typing import Any, Dict

from src.telegram.types import NormalizedTelegramUpdate


class TelegramUpdateNormalizationError(ValueError):
    """Raised when the webhook payload cannot be normalized."""


def _build_display_name(user_payload: Dict[str, Any]) -> str:
    first_name = user_payload.get("first_name", "") or ""
    last_name = user_payload.get("last_name", "") or ""
    return f"{first_name} {last_name}".strip()


def normalize_telegram_update(update: Dict[str, Any]) -> NormalizedTelegramUpdate:
    message = update.get("message")
    if not isinstance(message, dict):
        raise TelegramUpdateNormalizationError("Only message updates are supported in the current baseline.")

    sender = message.get("from")
    if not isinstance(sender, dict) or not sender.get("id"):
        raise TelegramUpdateNormalizationError("Telegram message sender is required.")

    chat = message.get("chat")
    if not isinstance(chat, dict) or not chat.get("id"):
        raise TelegramUpdateNormalizationError("Telegram chat is required.")

    content_type = "text"
    text = message.get("text")
    contact_payload = message.get("contact")
    contact_phone_number = None

    if isinstance(contact_payload, dict):
        content_type = "contact"
        contact_phone_number = contact_payload.get("phone_number")
    elif message.get("document"):
        content_type = "document"
    elif message.get("voice"):
        content_type = "voice"
    elif message.get("video") or message.get("video_note"):
        content_type = "video"
    elif text is None:
        content_type = "unknown"

    update_id = update.get("update_id")
    if update_id is None:
        raise TelegramUpdateNormalizationError("Telegram update_id is required.")

    return NormalizedTelegramUpdate(
        update_id=int(update_id),
        telegram_user_id=int(sender["id"]),
        telegram_chat_id=int(chat["id"]),
        message_id=message.get("message_id"),
        content_type=content_type,
        text=text.strip() if isinstance(text, str) else None,
        contact_phone_number=contact_phone_number,
        display_name=_build_display_name(sender) or None,
        username=sender.get("username"),
        language_code=sender.get("language_code"),
        payload=update,
    )

