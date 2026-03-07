from src.db.base import Base
from src.db.models import core  # noqa: F401


def test_core_table_names_present() -> None:
    expected = {
        "users",
        "user_consents",
        "files",
        "raw_messages",
        "state_transition_logs",
        "job_execution_logs",
        "notifications",
        "outbox_events",
    }

    assert expected.issubset(set(Base.metadata.tables.keys()))
