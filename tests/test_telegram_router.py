from types import SimpleNamespace

from fastapi.testclient import TestClient

from apps.api.main import create_app
from src.db.dependencies import get_db_session
from src.jobs.queue import JobMessage
from src.telegram.processing import TelegramProcessingService


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeQueueClient:
    def __init__(self, _session):
        self.messages = []

    def enqueue(self, message: JobMessage) -> None:
        self.messages.append(message)


def _private_text_update(*, update_id: int = 1, text: str = "/start") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 10,
            "from": {
                "id": 12345,
                "first_name": "Vlad",
                "last_name": "Golub",
                "username": "vladigolub",
                "language_code": "en",
            },
            "chat": {"id": 12345, "type": "private"},
            "text": text,
        },
    }


def test_webhook_queues_update_when_async_processing_enabled(monkeypatch) -> None:
    import src.telegram.router as telegram_router_module

    queue_client = FakeQueueClient(None)
    monkeypatch.setattr(
        telegram_router_module,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_webhook_secret="",
            telegram_enqueue_updates_enabled=True,
        ),
    )
    monkeypatch.setattr(telegram_router_module, "DatabaseQueueClient", lambda _db: queue_client)

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    client = TestClient(app)

    response = client.post("/telegram/webhook", json=_private_text_update(update_id=101))

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert len(queue_client.messages) == 1
    assert queue_client.messages[0].job_type == "telegram_update_process_v1"
    assert queue_client.messages[0].idempotency_key == "telegram:update:101"


def test_webhook_ignores_non_private_chat_before_queue(monkeypatch) -> None:
    import src.telegram.router as telegram_router_module

    queue_client = FakeQueueClient(None)
    monkeypatch.setattr(
        telegram_router_module,
        "get_settings",
        lambda: SimpleNamespace(
            telegram_webhook_secret="",
            telegram_enqueue_updates_enabled=True,
        ),
    )
    monkeypatch.setattr(telegram_router_module, "DatabaseQueueClient", lambda _db: queue_client)

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: FakeSession()
    client = TestClient(app)

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 102,
            "message": {
                "message_id": 11,
                "from": {"id": 12345, "first_name": "Vlad"},
                "chat": {"id": -100123, "type": "group", "title": "Helly Admin"},
                "text": "hi",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored_non_private_chat"
    assert queue_client.messages == []


def test_telegram_processing_service_replays_update_into_update_service(monkeypatch) -> None:
    import src.telegram.service as telegram_service_module

    captured = {}

    class FakeUpdateService:
        def __init__(self, _session):
            return None

        def process(self, normalized_update):
            captured["update_id"] = normalized_update.update_id
            captured["text"] = normalized_update.text
            return SimpleNamespace(status="processed", deduplicated=False, user_id="user-1")

    monkeypatch.setattr(telegram_service_module, "TelegramUpdateService", FakeUpdateService)

    result = TelegramProcessingService(object()).process_job(
        SimpleNamespace(
            job_type="telegram_update_process_v1",
            payload_json={"update": _private_text_update(update_id=103, text="Candidate")},
        )
    )

    assert captured == {"update_id": 103, "text": "Candidate"}
    assert result == {"status": "processed", "deduplicated": False, "user_id": "user-1"}
