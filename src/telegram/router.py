from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.db.dependencies import get_db_session
from src.monitoring.telegram_alerts import TelegramErrorAlertService
from src.telegram.normalizer import (
    TelegramUpdateNormalizationError,
    normalize_telegram_update,
)
from src.telegram.service import TelegramUpdateService

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    update: dict,
    db: Session = Depends(get_db_session),
    x_telegram_bot_api_secret_token: str = Header(default=""),
) -> dict:
    settings = get_settings()

    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret.",
            )

    try:
        normalized_update = normalize_telegram_update(update)
    except TelegramUpdateNormalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        result = TelegramUpdateService(db).process(normalized_update)
    except Exception as exc:
        TelegramErrorAlertService().send_error_alert(
            source="telegram_webhook",
            summary="Telegram webhook update processing failed.",
            exc=exc,
            context={
                "update_id": update.get("update_id"),
                "telegram_user_id": normalized_update.telegram_user_id,
                "telegram_chat_id": normalized_update.telegram_chat_id,
                "message_id": normalized_update.message_id,
                "chat_type": normalized_update.chat_type,
                "chat_title": normalized_update.chat_title,
            },
        )
        db.rollback()
        raise

    return {
        "ok": True,
        "status": result.status,
        "deduplicated": result.deduplicated,
        "notification_templates": result.notification_templates,
        "user_id": result.user_id,
    }
