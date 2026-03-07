from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    if not settings.supabase_db_url:
        raise RuntimeError("SUPABASE_DB_URL is not configured.")
    return create_engine(
        settings.supabase_db_url,
        pool_pre_ping=True,
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
