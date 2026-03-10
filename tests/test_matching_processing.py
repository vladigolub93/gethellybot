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
    def __init__(self, vacancy=None):
        self.vacancy = vacancy

    def get_open_vacancies(self):
        return []

    def get_by_id(self, vacancy_id):
        if self.vacancy is None:
            return None
        if str(getattr(self.vacancy, "id", "")) == str(vacancy_id):
            return self.vacancy
        return None


class FakeMatchingRepository:
    def __init__(self, active_matches=None):
        self.active_matches = list(active_matches or [])

    def list_active_for_vacancy(self, vacancy_id):
        return list(self.active_matches)


class FakeNotificationsRepository:
    def __init__(self):
        self.rows = []

    def create(self, **kwargs):
        self.rows.append(SimpleNamespace(**kwargs))
        return self.rows[-1]


class FakeMatchingService:
    def __init__(self, result=None):
        self.result = result or {
            "matching_run_id": "run-1",
            "candidate_pool_count": 10,
            "hard_filtered_count": 6,
            "shortlisted_count": 3,
        }

    def execute_for_vacancy(self, **kwargs):
        return {**self.result, "vacancy_id": kwargs["vacancy_id"]}


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
    service.matching = FakeMatchingRepository()
    service.notifications = FakeNotificationsRepository()
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
    service.matching = FakeMatchingRepository()
    service.notifications = FakeNotificationsRepository()
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
    service.matching = FakeMatchingRepository()
    service.notifications = FakeNotificationsRepository()
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


def test_matching_processing_notifies_manager_after_manual_refresh_with_new_candidates() -> None:
    service = MatchingProcessingService(FakeSession())
    service.queue = FakeQueue()
    service.vacancies = FakeVacanciesRepository(
        vacancy=SimpleNamespace(id="vacancy-1", manager_user_id="manager-1")
    )
    service.matching = FakeMatchingRepository()
    service.notifications = FakeNotificationsRepository()
    service.matching_service = FakeMatchingService(
        result={
            "matching_run_id": "run-2",
            "candidate_pool_count": 4,
            "hard_filtered_count": 2,
            "shortlisted_count": 2,
        }
    )

    service.process_job(
        SimpleNamespace(
            job_type="matching_run_for_vacancy_v1",
            payload_json={"vacancy_id": "vacancy-1", "trigger_type": "manager_manual_request"},
        )
    )

    assert len(service.notifications.rows) == 1
    notification = service.notifications.rows[0]
    assert notification.user_id == "manager-1"
    assert notification.template_key == "vacancy_open"
    assert notification.allow_duplicate is True
    assert "found 2 strong candidates" in notification.payload_json["text"].lower()
    assert "inviting the top 2" in notification.payload_json["text"].lower()


def test_matching_processing_notifies_manager_when_no_new_candidates_but_active_pipeline_exists() -> None:
    service = MatchingProcessingService(FakeSession())
    service.queue = FakeQueue()
    service.vacancies = FakeVacanciesRepository(
        vacancy=SimpleNamespace(id="vacancy-1", manager_user_id="manager-1")
    )
    service.matching = FakeMatchingRepository(
        active_matches=[SimpleNamespace(id="m-1"), SimpleNamespace(id="m-2")]
    )
    service.notifications = FakeNotificationsRepository()
    service.matching_service = FakeMatchingService(
        result={
            "matching_run_id": "run-3",
            "candidate_pool_count": 0,
            "hard_filtered_count": 0,
            "shortlisted_count": 0,
        }
    )

    service.process_job(
        SimpleNamespace(
            job_type="matching_run_for_vacancy_v1",
            payload_json={"vacancy_id": "vacancy-1", "trigger_type": "manager_manual_request"},
        )
    )

    assert len(service.notifications.rows) == 1
    text = service.notifications.rows[0].payload_json["text"].lower()
    assert "didn't find new strong candidates" in text
    assert "there are 2 candidates already in progress" in text
