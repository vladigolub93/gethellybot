from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.config.settings import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    if not settings.effective_supabase_db_url:
        raise RuntimeError("SUPABASE_DB_URL is not configured.")
    if settings.effective_db_use_null_pool:
        return create_engine(
            settings.effective_supabase_db_url,
            pool_pre_ping=True,
            poolclass=NullPool,
            future=True,
        )
    return create_engine(
        settings.effective_supabase_db_url,
        pool_pre_ping=True,
        pool_size=settings.effective_db_pool_size,
        max_overflow=settings.effective_db_pool_max_overflow,
        pool_timeout=settings.effective_db_pool_timeout_seconds,
        future=True,
    )


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        class_=Session,
        bind=get_engine(),
    )
