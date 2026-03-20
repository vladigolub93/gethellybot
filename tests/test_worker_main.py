from types import SimpleNamespace

import pytest

import apps.worker.main as worker_main


class FakeSession:
    def __init__(self) -> None:
        self.rollback_calls = 0
        self.commit_calls = 0
        self.close_calls = 0

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.close_calls += 1


class FakeJobRepo:
    def __init__(self, job) -> None:
        self.job = job
        self.failed = []

    def claim_next_queued(self):
        return self.job

    def mark_started(self, _job):
        return None

    def get_by_id(self, _job_id):
        return self.job

    def mark_failed(self, job, *, error_message: str):
        self.failed.append((job, error_message))
        return job


class FakeAlertService:
    def __init__(self, sink) -> None:
        self.sink = sink

    def send_error_alert(self, **kwargs):
        self.sink.append(kwargs)
        return True


def test_process_once_sends_error_alert_when_job_fails(monkeypatch) -> None:
    job = SimpleNamespace(
        id="job-1",
        job_type="matching_run_for_vacancy_v1",
        entity_type="vacancy",
        entity_id="vacancy-1",
    )
    primary_session = FakeSession()
    recovery_session = FakeSession()
    sessions = iter([primary_session, recovery_session])
    repo = FakeJobRepo(job)
    alerts = []

    monkeypatch.setattr(worker_main, "get_session_factory", lambda: lambda: next(sessions))
    monkeypatch.setattr(worker_main, "JobExecutionLogsRepository", lambda session: repo)
    monkeypatch.setattr(
        worker_main,
        "process_job",
        lambda session, claimed_job: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(worker_main, "TelegramErrorAlertService", lambda: FakeAlertService(alerts))

    with pytest.raises(RuntimeError, match="boom"):
        worker_main.process_once()

    assert repo.failed[0][1] == "boom"
    assert alerts[0]["source"] == "worker_process_once"
    assert alerts[0]["context"]["job_type"] == "matching_run_for_vacancy_v1"


def test_process_batch_drains_until_queue_is_empty(monkeypatch) -> None:
    results = iter([True, True, False])
    monkeypatch.setattr(worker_main, "process_once", lambda: next(results))

    processed_jobs = worker_main.process_batch(max_jobs=10)

    assert processed_jobs == 2


def test_process_batch_stops_at_max_jobs(monkeypatch) -> None:
    monkeypatch.setattr(worker_main, "process_once", lambda: True)

    processed_jobs = worker_main.process_batch(max_jobs=3)

    assert processed_jobs == 3
