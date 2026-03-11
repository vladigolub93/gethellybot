from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.db.base import Base
from src.db.models.core import User
from src.db.repositories.users import UsersRepository


def _make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function(
            "now",
            0,
            lambda: datetime.now(timezone.utc).isoformat(),
        )

    Base.metadata.create_all(engine, tables=[User.__table__])
    return Session(engine)


def test_create_or_update_from_telegram_stores_private_chat_id() -> None:
    session = _make_session()
    try:
        repo = UsersRepository(session)

        user = repo.create_or_update_from_telegram(
            telegram_user_id=100,
            telegram_chat_id=200,
            display_name="Test User",
            username="testuser",
            language_code="en",
            chat_type="private",
        )

        assert user.telegram_chat_id == 200
    finally:
        session.close()


def test_create_or_update_from_telegram_does_not_override_private_chat_with_group_chat() -> None:
    session = _make_session()
    try:
        repo = UsersRepository(session)
        user = repo.create_or_update_from_telegram(
            telegram_user_id=100,
            telegram_chat_id=200,
            display_name="Test User",
            username="testuser",
            language_code="en",
            chat_type="private",
        )

        updated = repo.create_or_update_from_telegram(
            telegram_user_id=100,
            telegram_chat_id=-100123,
            display_name="Test User",
            username="testuser",
            language_code="en",
            chat_type="supergroup",
        )

        assert updated.id == user.id
        assert updated.telegram_chat_id == 200
    finally:
        session.close()
