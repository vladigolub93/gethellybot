from types import SimpleNamespace
from uuid import uuid4

from src.admin.service import AdminService
from src.admin.session import AdminSessionContext


class FakeSession:
    def __init__(self):
        self.commit_calls = 0

    def commit(self):
        self.commit_calls += 1


class FakeNotificationsRepository:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id=uuid4(), **kwargs)


def _admin_context() -> AdminSessionContext:
    return AdminSessionContext(role="admin", issued_at=1, expires_at=9999999999)


def test_send_message_commits_created_notifications() -> None:
    service = AdminService(FakeSession())
    service.notifications = FakeNotificationsRepository()
    service.preview_message = lambda *args, **kwargs: {
        "message": {"text": "Broadcast from admin"},
        "deliverable": [
            {
                "userId": str(uuid4()),
                "telegramUserId": 123,
                "displayName": "User One",
                "username": "user1",
                "telegramChatId": 123,
            }
        ],
        "skipped": [],
        "counts": {"selected": 1, "deliverable": 1, "skipped": 0},
    }

    result = service.send_message(
        _admin_context(),
        user_ids=["placeholder"],
        message_text="Broadcast from admin",
    )

    assert result["status"] == "ok"
    assert len(service.notifications.calls) == 1
    assert service.session.commit_calls == 1


def test_block_users_commits_changes() -> None:
    user = SimpleNamespace(id=uuid4(), is_blocked=False, blocked_reason=None)
    service = AdminService(FakeSession())
    service._resolve_users_for_ids = lambda user_ids: [user]
    service._cancel_pending_notifications_for_user = lambda user_id: 0
    service.users = SimpleNamespace(
        set_blocked=lambda target, blocked, reason=None: (
            setattr(target, "is_blocked", blocked),
            setattr(target, "blocked_reason", reason),
        )
    )

    result = service.block_users(
        _admin_context(),
        user_ids=[str(user.id)],
        reason="admin test",
    )

    assert result["status"] == "ok"
    assert user.is_blocked is True
    assert user.blocked_reason == "admin test"
    assert service.session.commit_calls == 1
