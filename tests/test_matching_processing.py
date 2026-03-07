from types import SimpleNamespace

from src.matching.processing import MatchingProcessingService


class FakeSession:
    pass


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


class FakeVacanciesRepository:
    def get_open_vacancies(self):
        return []


class FakeMatchingService:
    def execute_for_vacancy(self, **kwargs):
        return {
            "matching_run_id": "run-1",
            "vacancy_id": kwargs["vacancy_id"],
            "candidate_pool_count": 10,
            "hard_filtered_count": 6,
            "shortlisted_count": 3,
        }


class FakeInviteWaveService:
    def send_wave_reminders(self, *, wave_id):
        return {
            "invite_wave_id": wave_id,
            "reminder_sent_count": 2,
        }

    def evaluate_wave(self, *, wave_id):
        return {
            "invite_wave_id": wave_id,
            "completed_interviews_count": 1,
            "expansion_enqueued": True,
        }


def test_matching_processing_enqueues_invite_dispatch_with_matching_run_id() -> None:
    service = MatchingProcessingService(FakeSession())
    service.queue = FakeQueue()
    service.vacancies = FakeVacanciesRepository()
    service.matching_service = FakeMatchingService()

    result = service.process_job(
        SimpleNamespace(
            job_type="matching_run_for_vacancy_v1",
            payload_json={"vacancy_id": "vacancy-1", "trigger_type": "vacancy_open"},
        )
    )

    assert result["matching_run_id"] == "run-1"
    assert len(service.queue.messages) == 1
    queued = service.queue.messages[0]
    assert queued.job_type == "interview_dispatch_invites_v1"
    assert queued.payload["vacancy_id"] == "vacancy-1"
    assert queued.payload["matching_run_id"] == "run-1"
    assert queued.payload["limit"] == 3


def test_matching_processing_routes_invite_wave_evaluation_job() -> None:
    service = MatchingProcessingService(FakeSession())
    service.queue = FakeQueue()
    service.vacancies = FakeVacanciesRepository()
    service.matching_service = FakeMatchingService()
    service.wave_service = FakeInviteWaveService()

    result = service.process_job(
        SimpleNamespace(
            job_type="matching_evaluate_invite_wave_v1",
            payload_json={"invite_wave_id": "wave-1"},
        )
    )

    assert result["invite_wave_id"] == "wave-1"
    assert result["expansion_enqueued"] is True


def test_matching_processing_routes_invite_wave_reminder_job() -> None:
    service = MatchingProcessingService(FakeSession())
    service.queue = FakeQueue()
    service.vacancies = FakeVacanciesRepository()
    service.matching_service = FakeMatchingService()
    service.wave_service = FakeInviteWaveService()

    result = service.process_job(
        SimpleNamespace(
            job_type="matching_send_invite_wave_reminder_v1",
            payload_json={"invite_wave_id": "wave-1"},
        )
    )

    assert result["invite_wave_id"] == "wave-1"
    assert result["reminder_sent_count"] == 2
