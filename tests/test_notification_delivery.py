from __future__ import annotations

from types import SimpleNamespace

from src.notifications.delivery import NotificationDeliveryService


class FakeNotificationsRepository:
    def __init__(self):
        self.rows = {}

    def get_by_id(self, notification_id):
        return self.rows.get(str(notification_id))

    def claim_for_send(self, notification_id):
        row = self.rows.get(str(notification_id))
        if row is None or row.status not in {"pending", "queued"}:
            return None
        row.status = "sending"
        return row

    def mark_sent(self, notification):
        notification.status = "sent"
        return notification

    def mark_failed(self, notification, *, error_message: str):
        notification.status = "failed"
        notification.last_error = error_message
        return notification


class FakeUsersRepository:
    def __init__(self, user):
        self.user = user

    def get_by_id(self, _user_id):
        return self.user


class FakeRawMessagesRepository:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(**kwargs)


class FakeTelegramBotClient:
    def __init__(self):
        self.calls = []

    def send_text_message(self, *, chat_id, text, reply_markup=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        return {"message_id": len(self.calls)}


def _build_service():
    service = NotificationDeliveryService(session=None)
    service.notifications = FakeNotificationsRepository()
    service.users = FakeUsersRepository(
        SimpleNamespace(id="user-1", telegram_chat_id=12345),
    )
    service.raw_messages = FakeRawMessagesRepository()
    service.telegram = FakeTelegramBotClient()
    return service


def test_send_notification_by_id_sends_only_once() -> None:
    service = _build_service()
    notification = SimpleNamespace(
        id="notification-1",
        user_id="user-1",
        template_key="request_role",
        payload_json={"text": "Choose your role."},
        status="pending",
    )
    service.notifications.rows[str(notification.id)] = notification

    first_result = service.send_notification_by_id(notification.id)
    second_result = service.send_notification_by_id(notification.id)

    assert first_result["status"] == "sent"
    assert second_result["status"] == "already_sent"
    assert len(service.telegram.calls) == 1


def test_send_notification_by_id_skips_when_already_claimed() -> None:
    service = _build_service()
    notification = SimpleNamespace(
        id="notification-2",
        user_id="user-1",
        template_key="request_role",
        payload_json={"text": "Choose your role."},
        status="sending",
    )
    service.notifications.rows[str(notification.id)] = notification

    result = service.send_notification_by_id(notification.id)

    assert result["status"] == "already_claimed"
    assert result["notification_status"] == "sending"
    assert service.telegram.calls == []
