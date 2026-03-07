from functools import lru_cache

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
