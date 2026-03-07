from os.path import splitext
from typing import Any, Dict, Optional

from src.telegram.types import NormalizedTelegramFile, NormalizedTelegramUpdate


class TelegramUpdateNormalizationError(ValueError):
    """Raised when the webhook payload cannot be normalized."""


def _build_display_name(user_payload: Dict[str, Any]) -> str:
    first_name = user_payload.get("first_name", "") or ""
    last_name = user_payload.get("last_name", "") or ""
    return f"{first_name} {last_name}".strip()


def _normalize_extension(file_name: Optional[str], mime_type: Optional[str]) -> Optional[str]:
    if file_name:
        extension = splitext(file_name)[1].lstrip(".").lower()
        if extension:
            return extension

    if mime_type == "audio/ogg":
        return "ogg"
    if mime_type == "video/mp4":
        return "mp4"

    return None


def _build_file_payload(kind: str, payload: Dict[str, Any]) -> NormalizedTelegramFile:
    file_name = payload.get("file_name")
    mime_type = payload.get("mime_type")
    return NormalizedTelegramFile(
        kind=kind,
        telegram_file_id=payload["file_id"],
        telegram_unique_file_id=payload.get("file_unique_id"),
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=payload.get("file_size"),
        extension=_normalize_extension(file_name, mime_type),
        payload=payload,
    )


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
    text = message.get("text") or message.get("caption")
    contact_payload = message.get("contact")
    document_payload = message.get("document")
    voice_payload = message.get("voice")
    video_payload = message.get("video") or message.get("video_note")
    contact_phone_number = None
    file = None

    if isinstance(contact_payload, dict):
        content_type = "contact"
        contact_phone_number = contact_payload.get("phone_number")
    elif isinstance(document_payload, dict):
        content_type = "document"
        file = _build_file_payload("document", document_payload)
    elif isinstance(voice_payload, dict):
        content_type = "voice"
        file = _build_file_payload("voice", voice_payload)
    elif isinstance(video_payload, dict):
        content_type = "video"
        file = _build_file_payload("video", video_payload)
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
        file=file,
        payload=update,
    )
