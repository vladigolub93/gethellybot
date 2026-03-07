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
        self.matches = []
        self.reminder_updates = []

    def get_wave_by_id(self, wave_id):
        return self.wave if self.wave.id == wave_id else None

    def count_shortlisted_for_vacancy(self, vacancy_id):
        return self.remaining_shortlisted_count

    def list_by_ids(self, match_ids):
        return [row for row in self.matches if str(row.id) in {str(item) for item in match_ids}]

    def mark_invitation_expired(self, match):
        match.status = "expired"
        return match

    def complete_invite_wave(self, wave, **kwargs):
        for key, value in kwargs.items():
            setattr(wave, key, value)
        self.completed.append({"wave": wave, **kwargs})
        return wave

    def mark_wave_reminder_sent(self, wave, *, payload_json=None):
        if payload_json is not None:
            wave.payload_json = payload_json
        self.reminder_updates.append({"wave": wave, "payload_json": payload_json})
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


class FakeCandidateRepository:
    def __init__(self, candidate):
        self.candidate = candidate

    def get_by_id(self, profile_id):
        return self.candidate if self.candidate.id == profile_id else None


class FakeNotificationsRepository:
    def __init__(self):
        self.rows = []

    def create(self, **kwargs):
        self.rows.append(SimpleNamespace(**kwargs))
        return self.rows[-1]


class FakeVacancyRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_by_id(self, vacancy_id):
        return self.vacancy if self.vacancy.id == vacancy_id else None


class FakeMessaging:
    def compose(self, approved_intent: str) -> str:
        return approved_intent


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


def test_send_wave_reminders_only_for_still_invited_matches() -> None:
    candidate = SimpleNamespace(id=uuid4(), user_id=uuid4())
    vacancy = SimpleNamespace(id=uuid4(), role_title="Backend Engineer")
    invited_match = SimpleNamespace(id=uuid4(), candidate_profile_id=candidate.id, status="invited")
    accepted_match = SimpleNamespace(id=uuid4(), candidate_profile_id=candidate.id, status="accepted")
    wave = SimpleNamespace(
        id=uuid4(),
        vacancy_id=vacancy.id,
        matching_run_id=uuid4(),
        wave_no=1,
        invited_count=2,
        completed_interviews_count=0,
        status="running",
        payload_json={"invited_match_ids": [str(invited_match.id), str(accepted_match.id)]},
    )
    service = InviteWaveService(FakeSession(), policy=WavePolicy())
    service.matching = FakeMatchingRepository(wave)
    service.matching.matches = [invited_match, accepted_match]
    service.candidates = FakeCandidateRepository(candidate)
    service.vacancies = FakeVacancyRepository(vacancy)
    service.notifications = FakeNotificationsRepository()
    service.messaging = FakeMessaging()

    result = service.send_wave_reminders(wave_id=wave.id)

    assert result["reminder_sent_count"] == 1
    assert result["reminded_match_ids"] == [str(invited_match.id)]
    assert len(service.notifications.rows) == 1
    assert service.notifications.rows[0].template_key == "candidate_interview_invitation_reminder"
    assert "reply with 'Accept interview'" in service.notifications.rows[0].payload_json["text"]


def test_evaluate_wave_expires_still_invited_matches() -> None:
    invited_match = SimpleNamespace(id=uuid4(), candidate_profile_id=uuid4(), status="invited")
    accepted_match = SimpleNamespace(id=uuid4(), candidate_profile_id=uuid4(), status="accepted")
    wave = SimpleNamespace(
        id=uuid4(),
        vacancy_id=uuid4(),
        matching_run_id=uuid4(),
        wave_no=1,
        invited_count=2,
        completed_interviews_count=0,
        status="running",
        payload_json={"invited_match_ids": [str(invited_match.id), str(accepted_match.id)]},
    )
    service = InviteWaveService(FakeSession(), policy=WavePolicy(target_completed_interviews=2, expansion_wave_size=2))
    service.matching = FakeMatchingRepository(wave)
    service.matching.matches = [invited_match, accepted_match]
    service.matching.remaining_shortlisted_count = 0
    service.interviews = FakeInterviewsRepository(completed_count=1)
    service.queue = FakeQueue()

    result = service.evaluate_wave(wave_id=wave.id)

    assert invited_match.status == "expired"
    assert accepted_match.status == "accepted"
    assert result["expired_match_ids"] == [str(invited_match.id)]
