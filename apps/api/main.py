from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config.logging import configure_logging
from src.config.settings import get_settings
from src.health.router import router as health_router
from src.telegram.router import router as telegram_router
from src.webapp.router import router as webapp_router
from src.webapp.service import WEBAPP_STATIC_DIR


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
    )
    app.mount("/webapp/assets", StaticFiles(directory=str(WEBAPP_STATIC_DIR)), name="webapp-assets")
    app.include_router(health_router)
    app.include_router(telegram_router)
    app.include_router(webapp_router)

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "environment": settings.app_env,
            "status": "ok",
        }

    return app


app = create_app()
