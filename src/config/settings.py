from functools import lru_cache
from typing import Optional, Set

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="helly", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_base_url: str = Field(default="http://localhost:8000", alias="APP_BASE_URL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("API_PORT", "PORT"),
    )

    worker_poll_interval_seconds: int = Field(
        default=5, alias="WORKER_POLL_INTERVAL_SECONDS"
    )
    scheduler_poll_interval_seconds: int = Field(
        default=15, alias="SCHEDULER_POLL_INTERVAL_SECONDS"
    )

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_error_chat_id: Optional[int] = Field(default=None, alias="TELEGRAM_ERROR_CHAT_ID")
    telegram_webapp_session_secret: str = Field(
        default="",
        alias="TELEGRAM_WEBAPP_SESSION_SECRET",
    )
    telegram_webapp_admin_user_ids: str = Field(
        default="",
        alias="TELEGRAM_WEBAPP_ADMIN_USER_IDS",
    )
    telegram_webapp_auth_max_age_seconds: int = Field(
        default=86400,
        alias="TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS",
    )
    telegram_webapp_session_ttl_seconds: int = Field(
        default=86400,
        alias="TELEGRAM_WEBAPP_SESSION_TTL_SECONDS",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model_extraction: str = Field(
        default="gpt-5.4", alias="OPENAI_MODEL_EXTRACTION"
    )
    openai_model_reasoning: str = Field(
        default="gpt-5.4", alias="OPENAI_MODEL_REASONING"
    )
    openai_model_transcription: str = Field(
        default="gpt-4o-mini-transcribe", alias="OPENAI_MODEL_TRANSCRIPTION"
    )
    openai_model_embeddings: str = Field(
        default="text-embedding-3-small", alias="OPENAI_MODEL_EMBEDDINGS"
    )
    openai_embedding_dimensions: int = Field(
        default=256, alias="OPENAI_EMBEDDING_DIMENSIONS"
    )

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_db_url: str = Field(default="", alias="SUPABASE_DB_URL")
    supabase_service_role_key: str = Field(
        default="", alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_storage_bucket_private: str = Field(
        default="helly-private", alias="SUPABASE_STORAGE_BUCKET_PRIVATE"
    )
    db_use_null_pool: bool = Field(default=False, alias="DB_USE_NULL_POOL")
    db_pool_size: int = Field(default=2, alias="DB_POOL_SIZE")
    db_pool_max_overflow: int = Field(default=0, alias="DB_POOL_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, alias="DB_POOL_TIMEOUT_SECONDS")

    queue_backend: str = Field(default="database", alias="QUEUE_BACKEND")
    redis_url: str = Field(default="", alias="REDIS_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_dev(self) -> bool:
        return self.app_env in {"development", "local", "test"}

    @property
    def webapp_session_secret(self) -> str:
        return self.telegram_webapp_session_secret or self.telegram_bot_token

    @property
    def webapp_admin_telegram_user_ids(self) -> Set[int]:
        values = set()
        for raw_value in (self.telegram_webapp_admin_user_ids or "").replace(" ", "").split(","):
            if not raw_value:
                continue
            try:
                values.add(int(raw_value))
            except ValueError:
                continue
        return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
