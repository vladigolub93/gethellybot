from functools import lru_cache
from typing import Optional, Set

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    helly_process_type: str = Field(default="api", alias="HELLY_PROCESS_TYPE")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="helly", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_base_url: str = Field(default="http://localhost:8000", alias="APP_BASE_URL")
    admin_base_url: str = Field(default="", alias="ADMIN_BASE_URL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("API_PORT", "PORT"),
    )

    worker_poll_interval_seconds: int = Field(
        default=1, alias="WORKER_POLL_INTERVAL_SECONDS"
    )
    worker_concurrency: int = Field(
        default=1, alias="WORKER_CONCURRENCY"
    )
    scheduler_poll_interval_seconds: int = Field(
        default=2, alias="SCHEDULER_POLL_INTERVAL_SECONDS"
    )
    worker_max_jobs_per_tick: int = Field(
        default=50, alias="WORKER_MAX_JOBS_PER_TICK"
    )
    scheduler_dispatch_batch_size: int = Field(
        default=100, alias="SCHEDULER_DISPATCH_BATCH_SIZE"
    )
    scheduler_max_cycles_per_tick: int = Field(
        default=10, alias="SCHEDULER_MAX_CYCLES_PER_TICK"
    )

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_disable_outbound: bool = Field(
        default=False,
        alias="TELEGRAM_DISABLE_OUTBOUND",
    )
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_error_chat_id: Optional[int] = Field(default=None, alias="TELEGRAM_ERROR_CHAT_ID")
    telegram_immediate_job_flush_enabled: bool = Field(
        default=False,
        alias="TELEGRAM_IMMEDIATE_JOB_FLUSH_ENABLED",
    )
    telegram_enqueue_updates_enabled: bool = Field(
        default=False,
        alias="TELEGRAM_ENQUEUE_UPDATES_ENABLED",
    )
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
    admin_panel_pin: str = Field(default="", alias="ADMIN_PANEL_PIN")
    admin_session_secret: str = Field(default="", alias="ADMIN_SESSION_SECRET")
    admin_session_ttl_seconds: int = Field(default=86400, alias="ADMIN_SESSION_TTL_SECONDS")

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
    review_object_rag_enabled: bool = Field(
        default=True,
        alias="REVIEW_OBJECT_RAG_ENABLED",
    )

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_db_url: str = Field(default="", alias="SUPABASE_DB_URL")
    api_supabase_db_url: str = Field(default="", alias="API_SUPABASE_DB_URL")
    worker_supabase_db_url: str = Field(default="", alias="WORKER_SUPABASE_DB_URL")
    scheduler_supabase_db_url: str = Field(default="", alias="SCHEDULER_SUPABASE_DB_URL")
    supabase_service_role_key: str = Field(
        default="", alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_storage_bucket_private: str = Field(
        default="helly-private", alias="SUPABASE_STORAGE_BUCKET_PRIVATE"
    )
    db_use_null_pool: bool = Field(default=False, alias="DB_USE_NULL_POOL")
    api_db_use_null_pool: Optional[bool] = Field(default=None, alias="API_DB_USE_NULL_POOL")
    worker_db_use_null_pool: Optional[bool] = Field(default=None, alias="WORKER_DB_USE_NULL_POOL")
    scheduler_db_use_null_pool: Optional[bool] = Field(default=None, alias="SCHEDULER_DB_USE_NULL_POOL")
    db_pool_size: int = Field(default=2, alias="DB_POOL_SIZE")
    api_db_pool_size: Optional[int] = Field(default=None, alias="API_DB_POOL_SIZE")
    worker_db_pool_size: Optional[int] = Field(default=None, alias="WORKER_DB_POOL_SIZE")
    scheduler_db_pool_size: Optional[int] = Field(default=None, alias="SCHEDULER_DB_POOL_SIZE")
    db_pool_max_overflow: int = Field(default=0, alias="DB_POOL_MAX_OVERFLOW")
    api_db_pool_max_overflow: Optional[int] = Field(default=None, alias="API_DB_POOL_MAX_OVERFLOW")
    worker_db_pool_max_overflow: Optional[int] = Field(default=None, alias="WORKER_DB_POOL_MAX_OVERFLOW")
    scheduler_db_pool_max_overflow: Optional[int] = Field(default=None, alias="SCHEDULER_DB_POOL_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, alias="DB_POOL_TIMEOUT_SECONDS")
    api_db_pool_timeout_seconds: Optional[int] = Field(default=None, alias="API_DB_POOL_TIMEOUT_SECONDS")
    worker_db_pool_timeout_seconds: Optional[int] = Field(default=None, alias="WORKER_DB_POOL_TIMEOUT_SECONDS")
    scheduler_db_pool_timeout_seconds: Optional[int] = Field(default=None, alias="SCHEDULER_DB_POOL_TIMEOUT_SECONDS")

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

    @property
    def effective_admin_panel_pin(self) -> str:
        return self.admin_panel_pin or "6088"

    @property
    def effective_admin_session_secret(self) -> str:
        return self.admin_session_secret or self.webapp_session_secret or self.telegram_bot_token

    @property
    def effective_admin_base_url(self) -> str:
        return (self.admin_base_url or self.app_base_url).rstrip("/")

    @property
    def effective_process_type(self) -> str:
        return (self.helly_process_type or "api").strip().lower()

    def _select_process_value(self, *, api, worker, scheduler, default):
        if self.effective_process_type == "worker":
            return worker if worker is not None and worker != "" else default
        if self.effective_process_type == "scheduler":
            return scheduler if scheduler is not None and scheduler != "" else default
        return api if api is not None and api != "" else default

    @property
    def effective_supabase_db_url(self) -> str:
        return self._select_process_value(
            api=self.api_supabase_db_url,
            worker=self.worker_supabase_db_url,
            scheduler=self.scheduler_supabase_db_url,
            default=self.supabase_db_url,
        )

    @property
    def effective_db_use_null_pool(self) -> bool:
        return bool(
            self._select_process_value(
                api=self.api_db_use_null_pool,
                worker=self.worker_db_use_null_pool,
                scheduler=self.scheduler_db_use_null_pool,
                default=self.db_use_null_pool,
            )
        )

    @property
    def effective_db_pool_size(self) -> int:
        return int(
            self._select_process_value(
                api=self.api_db_pool_size,
                worker=self.worker_db_pool_size,
                scheduler=self.scheduler_db_pool_size,
                default=self.db_pool_size,
            )
        )

    @property
    def effective_db_pool_max_overflow(self) -> int:
        return int(
            self._select_process_value(
                api=self.api_db_pool_max_overflow,
                worker=self.worker_db_pool_max_overflow,
                scheduler=self.scheduler_db_pool_max_overflow,
                default=self.db_pool_max_overflow,
            )
        )

    @property
    def effective_db_pool_timeout_seconds(self) -> int:
        return int(
            self._select_process_value(
                api=self.api_db_pool_timeout_seconds,
                worker=self.worker_db_pool_timeout_seconds,
                scheduler=self.scheduler_db_pool_timeout_seconds,
                default=self.db_pool_timeout_seconds,
            )
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
