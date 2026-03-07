from types import SimpleNamespace
from uuid import uuid4

import apps.scheduler.main as scheduler_main


class FakeSession:
    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class FakeNotificationsRepository:
    def list_pending_dispatchable(self, limit=20):
        return []


class FakeFilesRepository:
    def list_pending_storage(self, limit=20):
        return []


class FakeMatchingRepository:
    def list_active_invite_waves(self, limit=20):
        return [
            SimpleNamespace(id=uuid4(), vacancy_id=uuid4()),
            SimpleNamespace(id=uuid4(), vacancy_id=uuid4()),
        ]


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


def test_scheduler_enqueues_invite_wave_evaluations(monkeypatch) -> None:
    fake_queue = FakeQueue()

    monkeypatch.setattr(scheduler_main, "get_session_factory", lambda: lambda: FakeSession())
    monkeypatch.setattr(scheduler_main, "NotificationsRepository", lambda session: FakeNotificationsRepository())
    monkeypatch.setattr(scheduler_main, "FilesRepository", lambda session: FakeFilesRepository())
    monkeypatch.setattr(scheduler_main, "MatchingRepository", lambda session: FakeMatchingRepository())
    monkeypatch.setattr(scheduler_main, "DatabaseQueueClient", lambda session: fake_queue)

    result = scheduler_main.dispatch_once()

    assert result["invite_wave_evaluations_enqueued"] == 2
    assert len(fake_queue.messages) == 2
    assert all(message.job_type == "matching_evaluate_invite_wave_v1" for message in fake_queue.messages)
