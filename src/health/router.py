from fastapi import APIRouter

from src.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/ready")
async def ready() -> dict:
    settings = get_settings()
    return {
        "status": "ready",
        "service": settings.app_name,
        "environment": settings.app_env,
        "checks": {
            "config_loaded": True,
        },
    }

