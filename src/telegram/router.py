from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.db.dependencies import get_db_session
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
    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "status": result.status,
        "deduplicated": result.deduplicated,
        "notification_templates": result.notification_templates,
        "user_id": result.user_id,
    }
