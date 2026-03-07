from types import SimpleNamespace
from uuid import uuid4

from src.matching.waves import InviteWaveService, WavePolicy


class FakeSession:
    pass


class FakeMatchingRepository:
    def __init__(self, wave):
        self.wave = wave
        self.completed = []
        self.remaining_shortlisted_count = 0

    def get_wave_by_id(self, wave_id):
        return self.wave if self.wave.id == wave_id else None

    def count_shortlisted_for_vacancy(self, vacancy_id):
        return self.remaining_shortlisted_count

    def complete_invite_wave(self, wave, **kwargs):
        for key, value in kwargs.items():
            setattr(wave, key, value)
        self.completed.append({"wave": wave, **kwargs})
        return wave


class FakeInterviewsRepository:
    def __init__(self, completed_count):
        self.completed_count = completed_count
        self.calls = []

    def count_completed_for_match_ids(self, match_ids):
        self.calls.append(match_ids)
        return self.completed_count


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


def test_evaluate_wave_completes_wave_without_expansion_if_threshold_met() -> None:
    wave = SimpleNamespace(
        id=uuid4(),
        vacancy_id=uuid4(),
        matching_run_id=uuid4(),
        wave_no=1,
        invited_count=3,
        completed_interviews_count=0,
        status="running",
        payload_json={"invited_match_ids": ["m1", "m2", "m3"]},
    )
    service = InviteWaveService(FakeSession(), policy=WavePolicy(target_completed_interviews=2, expansion_wave_size=2))
    service.matching = FakeMatchingRepository(wave)
    service.matching.remaining_shortlisted_count = 4
    service.interviews = FakeInterviewsRepository(completed_count=2)
    service.queue = FakeQueue()

    result = service.evaluate_wave(wave_id=wave.id)

    assert result["completed_interviews_count"] == 2
    assert result["remaining_shortlisted_count"] == 4
    assert result["shortlist_exhausted"] is False
    assert result["expansion_enqueued"] is False
    assert wave.status == "completed"
    assert not service.queue.messages


def test_evaluate_wave_enqueues_expansion_when_threshold_not_met() -> None:
    wave = SimpleNamespace(
        id=uuid4(),
        vacancy_id=uuid4(),
        matching_run_id=uuid4(),
        wave_no=1,
        invited_count=3,
        completed_interviews_count=0,
        status="running",
        payload_json={"invited_match_ids": ["m1", "m2", "m3"]},
    )
    service = InviteWaveService(FakeSession(), policy=WavePolicy(target_completed_interviews=2, expansion_wave_size=2))
    service.matching = FakeMatchingRepository(wave)
    service.matching.remaining_shortlisted_count = 3
    service.interviews = FakeInterviewsRepository(completed_count=1)
    service.queue = FakeQueue()

    result = service.evaluate_wave(wave_id=wave.id)

    assert result["completed_interviews_count"] == 1
    assert result["remaining_shortlisted_count"] == 3
    assert result["shortlist_exhausted"] is False
    assert result["expansion_enqueued"] is True
    assert len(service.queue.messages) == 1
    queued = service.queue.messages[0]
    assert queued.job_type == "interview_dispatch_invites_v1"
    assert queued.payload["vacancy_id"] == str(wave.vacancy_id)
    assert queued.payload["matching_run_id"] == str(wave.matching_run_id)
    assert queued.payload["limit"] == 2


def test_evaluate_wave_does_not_enqueue_expansion_when_shortlist_exhausted() -> None:
    wave = SimpleNamespace(
        id=uuid4(),
        vacancy_id=uuid4(),
        matching_run_id=uuid4(),
        wave_no=1,
        invited_count=3,
        completed_interviews_count=0,
        status="running",
        payload_json={"invited_match_ids": ["m1", "m2", "m3"]},
    )
    service = InviteWaveService(FakeSession(), policy=WavePolicy(target_completed_interviews=2, expansion_wave_size=2))
    service.matching = FakeMatchingRepository(wave)
    service.matching.remaining_shortlisted_count = 0
    service.interviews = FakeInterviewsRepository(completed_count=1)
    service.queue = FakeQueue()

    result = service.evaluate_wave(wave_id=wave.id)

    assert result["completed_interviews_count"] == 1
    assert result["remaining_shortlisted_count"] == 0
    assert result["shortlist_exhausted"] is True
    assert result["expansion_enqueued"] is False
    assert not service.queue.messages
