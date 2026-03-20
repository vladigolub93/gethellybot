from src.config.settings import Settings


def test_process_db_settings_fall_back_to_global_defaults() -> None:
    settings = Settings(
        HELLY_PROCESS_TYPE="api",
        SUPABASE_DB_URL="postgresql://global",
        DB_USE_NULL_POOL=False,
        DB_POOL_SIZE=2,
        DB_POOL_MAX_OVERFLOW=0,
        DB_POOL_TIMEOUT_SECONDS=30,
    )

    assert settings.effective_process_type == "api"
    assert settings.effective_supabase_db_url == "postgresql://global"
    assert settings.effective_db_use_null_pool is False
    assert settings.effective_db_pool_size == 2
    assert settings.effective_db_pool_max_overflow == 0
    assert settings.effective_db_pool_timeout_seconds == 30


def test_worker_process_db_settings_use_worker_overrides() -> None:
    settings = Settings(
        HELLY_PROCESS_TYPE="worker",
        SUPABASE_DB_URL="postgresql://global",
        WORKER_SUPABASE_DB_URL="postgresql://worker",
        DB_USE_NULL_POOL=False,
        WORKER_DB_USE_NULL_POOL=True,
        DB_POOL_SIZE=2,
        WORKER_DB_POOL_SIZE=7,
        DB_POOL_MAX_OVERFLOW=0,
        WORKER_DB_POOL_MAX_OVERFLOW=3,
        DB_POOL_TIMEOUT_SECONDS=30,
        WORKER_DB_POOL_TIMEOUT_SECONDS=12,
    )

    assert settings.effective_process_type == "worker"
    assert settings.effective_supabase_db_url == "postgresql://worker"
    assert settings.effective_db_use_null_pool is True
    assert settings.effective_db_pool_size == 7
    assert settings.effective_db_pool_max_overflow == 3
    assert settings.effective_db_pool_timeout_seconds == 12


def test_scheduler_process_db_settings_use_scheduler_overrides() -> None:
    settings = Settings(
        HELLY_PROCESS_TYPE="scheduler",
        SUPABASE_DB_URL="postgresql://global",
        SCHEDULER_SUPABASE_DB_URL="postgresql://scheduler",
        DB_USE_NULL_POOL=False,
        SCHEDULER_DB_USE_NULL_POOL=True,
        DB_POOL_SIZE=2,
        SCHEDULER_DB_POOL_SIZE=1,
        DB_POOL_MAX_OVERFLOW=0,
        SCHEDULER_DB_POOL_MAX_OVERFLOW=0,
        DB_POOL_TIMEOUT_SECONDS=30,
        SCHEDULER_DB_POOL_TIMEOUT_SECONDS=5,
    )

    assert settings.effective_process_type == "scheduler"
    assert settings.effective_supabase_db_url == "postgresql://scheduler"
    assert settings.effective_db_use_null_pool is True
    assert settings.effective_db_pool_size == 1
    assert settings.effective_db_pool_max_overflow == 0
    assert settings.effective_db_pool_timeout_seconds == 5
