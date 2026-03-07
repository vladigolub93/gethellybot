from types import SimpleNamespace
from uuid import uuid4

from src.vacancy.service import VacancyService
from src.vacancy.states import (
    VACANCY_STATE_CLARIFICATION_QA,
    VACANCY_STATE_INTAKE_PENDING,
    VACANCY_STATE_JD_PROCESSING,
    VACANCY_STATE_OPEN,
)


class FakeSession:
    def add(self, _obj):
        return None

    def flush(self):
        return None


class FakeVacanciesRepository:
    def __init__(self):
        self.vacancy = None
        self.versions = []

    def get_latest_incomplete_by_manager_user_id(self, _manager_user_id):
        return self.vacancy

    def create(self, *, manager_user_id, state):
        self.vacancy = SimpleNamespace(
            id=uuid4(),
            manager_user_id=manager_user_id,
            state=state,
            current_version_id=None,
            countries_allowed_json=[],
            primary_tech_stack_json=[],
            questions_context_json={},
            opened_at=None,
            budget_min=None,
            budget_max=None,
            budget_currency=None,
            budget_period=None,
            work_format=None,
            team_size=None,
            project_description=None,
            role_title=None,
            seniority_normalized=None,
            deleted_at=None,
        )
        return self.vacancy

    def get_latest_active_by_manager_user_id(self, manager_user_id):
        if self.vacancy and self.vacancy.manager_user_id == manager_user_id and self.vacancy.deleted_at is None:
            return self.vacancy
        return None

    def next_version_no(self, _vacancy_id):
        return len(self.versions) + 1

    def create_version(self, **kwargs):
        version = SimpleNamespace(id=uuid4(), **kwargs)
        self.versions.append(version)
        return version

    def set_current_version(self, vacancy, version_id):
        vacancy.current_version_id = version_id
        return vacancy

    def update_clarifications(self, vacancy, **kwargs):
        for key, value in kwargs.items():
            setattr(vacancy, key, value)
        return vacancy

    def update_questions_context(self, vacancy, questions_context_json):
        vacancy.questions_context_json = questions_context_json
        return vacancy

    def mark_open(self, vacancy):
        vacancy.opened_at = "now"
        return vacancy

    def soft_delete(self, vacancy):
        vacancy.deleted_at = "now"
        vacancy.state = "DELETED"
        return vacancy


class FakeStateService:
    def __init__(self):
        self.transitions = []

    def record_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def transition(self, **kwargs):
        entity = kwargs["entity"]
        field = kwargs.get("state_field", "state")
        setattr(entity, field, kwargs["to_state"])
        self.transitions.append(kwargs)


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


class FakeMatchingRepository:
    def __init__(self):
        self.active_matches = []

    def list_active_for_vacancy(self, vacancy_id):
        return [match for match in self.active_matches if match.vacancy_id == vacancy_id]


class FakeInterviewsRepository:
    def __init__(self):
        self.sessions_by_match_id = {}

    def get_active_by_match_id(self, match_id):
        return self.sessions_by_match_id.get(match_id)


def test_start_onboarding_moves_manager_to_intake_pending() -> None:
    service = VacancyService(FakeSession())
    service.repo = FakeVacanciesRepository()
    service.state_service = FakeStateService()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = service.start_onboarding(user, trigger_ref_id=uuid4())

    assert vacancy.state == VACANCY_STATE_INTAKE_PENDING


def test_handle_jd_intake_transitions_to_processing() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_INTAKE_PENDING)

    result = service.handle_jd_intake(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Senior Python Engineer for fintech platform",
    )

    assert result.status == "accepted"
    assert fake_repo.vacancy.state == VACANCY_STATE_JD_PROCESSING
    assert len(fake_repo.versions) == 1
    assert len(fake_queue.messages) == 1


def test_clarification_completion_opens_vacancy() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)

    result = service.handle_clarification_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text=(
            "Budget: $7000-$9000 per month. Countries: Poland and Germany. Remote. "
            "Team size: 6. Project: B2B payments platform. Primary stack: Python, FastAPI, PostgreSQL."
        ),
    )

    assert result is not None
    assert result.status == "completed"
    assert vacancy.state == VACANCY_STATE_OPEN
    assert vacancy.opened_at == "now"
    assert len(service.queue.messages) == 1


def test_clarification_requests_follow_up_when_partial() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)

    result = service.handle_clarification_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Remote, team size: 6",
    )

    assert result is not None
    assert result.status == "follow_up"
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA


def test_parsed_clarification_payload_opens_vacancy() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)

    result = service.handle_clarification_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "budget_min": 7000,
            "budget_max": 9000,
            "budget_currency": "USD",
            "budget_period": "month",
            "countries_allowed_json": ["PL", "DE"],
            "work_format": "remote",
            "team_size": 6,
            "project_description": "B2B payments platform.",
            "primary_tech_stack_json": ["python", "fastapi", "postgresql"],
        },
    )

    assert result is not None
    assert result.status == "completed"
    assert vacancy.state == VACANCY_STATE_OPEN


def test_vacancy_deletion_requires_confirmation_then_soft_deletes() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.interviews = FakeInterviewsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_OPEN)
    match = SimpleNamespace(id=uuid4(), vacancy_id=vacancy.id, status="manager_review")
    interview = SimpleNamespace(id=uuid4(), match_id=match.id, state="IN_PROGRESS")
    service.matching.active_matches.append(match)
    service.interviews.sessions_by_match_id[match.id] = interview

    first = service.handle_deletion_message(
        user=user,
        raw_message_id=uuid4(),
        text="delete vacancy",
    )
    second = service.handle_deletion_message(
        user=user,
        raw_message_id=uuid4(),
        text="confirm delete vacancy",
    )

    assert first is not None
    assert first.status == "confirmation_required"
    assert second is not None
    assert second.status == "deleted"
    assert vacancy.deleted_at == "now"
    assert vacancy.state == "DELETED"
    assert match.status == "cancelled"
    assert interview.state == "CANCELLED"
    assert len(service.queue.messages) == 1
    assert service.queue.messages[0].job_type == "cleanup_vacancy_deletion_v1"
