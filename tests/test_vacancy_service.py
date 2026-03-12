from types import SimpleNamespace
from uuid import uuid4

from src.vacancy.service import VacancyService
from src.vacancy.states import (
    VACANCY_STATE_CLARIFICATION_QA,
    VACANCY_STATE_INTAKE_PENDING,
    VACANCY_STATE_JD_PROCESSING,
    VACANCY_STATE_OPEN,
    VACANCY_STATE_SUMMARY_REVIEW,
)


class FakeSession:
    def add(self, _obj):
        return None

    def flush(self):
        return None


class FakeVacanciesRepository:
    def __init__(self):
        self.vacancy = None
        self.vacancies = []
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
        self.vacancies.append(self.vacancy)
        return self.vacancy

    def get_latest_active_by_manager_user_id(self, manager_user_id):
        for vacancy in reversed(self.vacancies):
            if vacancy.manager_user_id == manager_user_id and vacancy.deleted_at is None:
                return vacancy
        return None

    def get_by_manager_user_id(self, manager_user_id):
        return [
            vacancy
            for vacancy in self.vacancies
            if vacancy.manager_user_id == manager_user_id and vacancy.deleted_at is None
        ]

    def get_open_by_manager_user_id(self, manager_user_id):
        return [
            vacancy
            for vacancy in self.vacancies
            if vacancy.manager_user_id == manager_user_id
            and vacancy.deleted_at is None
            and vacancy.state == VACANCY_STATE_OPEN
        ]

    def next_version_no(self, _vacancy_id):
        return len(self.versions) + 1

    def create_version(self, **kwargs):
        payload = {
            "id": uuid4(),
            "approval_status": "draft",
            "approved_by_manager": False,
        }
        payload.update(kwargs)
        version = SimpleNamespace(**payload)
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

    def get_current_version(self, vacancy):
        if vacancy.current_version_id is None:
            return None
        for version in self.versions:
            if version.id == vacancy.current_version_id:
                return version
        return None

    def mark_version_approved(self, version):
        version.approval_status = "approved"
        version.approved_by_manager = True
        return version

    def count_versions_by_source_type(self, vacancy_id, source_type):
        return sum(1 for version in self.versions if version.vacancy_id == vacancy_id and version.source_type == source_type)


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


def test_execute_open_action_enqueues_matching_refresh() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    service.repo = fake_repo
    service.state_service = FakeStateService()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_OPEN)

    result = service.execute_open_action(
        user=user,
        raw_message_id="raw-open-1",
        action="find_matching_candidates",
    )

    assert result is not None
    assert result.status == "matching_requested"
    assert len(service.queue.messages) == 1
    assert service.queue.messages[0].job_type == "matching_run_for_vacancy_v1"
    assert service.queue.messages[0].payload["vacancy_id"] == str(vacancy.id)
    assert service.queue.messages[0].payload["trigger_type"] == "manager_manual_request"
    assert service.queue.messages[0].idempotency_key.endswith(":manual:raw-open-1")


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
    assert result.status == "next_question"
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert "remote" in result.notification_text.lower() or "office" in result.notification_text.lower()
    assert vacancy.budget_min == 7000
    assert vacancy.questions_context_json["current_question_key"] == "work_format"
    assert vacancy.opened_at is None
    assert len(service.queue.messages) == 0


def test_vacancy_summary_review_approve_moves_to_clarifications() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        vacancy_id=vacancy.id,
        version_no=1,
        source_type="pasted_text",
        approval_summary_text="Summary",
        summary_json={"approval_summary_text": "Summary"},
    )
    fake_repo.set_current_version(vacancy, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_summary",
    )

    assert result is not None
    assert result.status == "approved"
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert version.approval_status == "approved"
    assert vacancy.questions_context_json["current_question_key"] == "budget"
    assert vacancy.questions_context_json["confirmed_fields"] == []


def test_vacancy_summary_review_edit_queues_one_correction_round() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        vacancy_id=vacancy.id,
        version_no=1,
        source_type="pasted_text",
        approval_summary_text="Summary",
        summary_json={"approval_summary_text": "Summary"},
    )
    fake_repo.set_current_version(vacancy, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="request_summary_change",
        structured_payload={"edit_text": "The role is Go-first, not Python-first."},
    )

    assert result is not None
    assert result.status == "edit_processing"
    assert vacancy.state == VACANCY_STATE_JD_PROCESSING
    assert fake_queue.messages
    assert fake_queue.messages[-1].job_type == "vacancy_summary_edit_apply_v1"


def test_execute_vacancy_summary_review_action_approve_moves_to_clarification() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        vacancy_id=vacancy.id,
        version_no=1,
        source_type="pasted_text",
        approval_summary_text="Summary",
        summary_json={"approval_summary_text": "Summary"},
    )
    fake_repo.set_current_version(vacancy, version.id)

    result = service.execute_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_summary",
    )

    assert result is not None
    assert result.status == "approved"
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert version.approval_status == "approved"
    assert vacancy.questions_context_json["current_question_key"] == "budget"
    assert vacancy.questions_context_json["confirmed_fields"] == []


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
    assert result.status in {"follow_up", "next_question"}
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert result.notification_text


def test_clarification_asks_next_question_in_sequence() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)
    fake_repo.update_questions_context(
        vacancy,
        {
            "follow_up_used": {
                "budget": False,
                "countries": False,
                "work_format": False,
                "team_size": False,
                "project_description": False,
                "primary_tech_stack": False,
            },
            "confirmed_fields": [],
            "current_question_key": "budget",
        },
    )

    result = service.handle_clarification_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "budget_min": 7000,
            "budget_max": 9000,
            "budget_currency": "USD",
            "budget_period": "month",
        },
    )

    assert result is not None
    assert result.status == "next_question"
    assert "remote" in result.notification_text.lower() or "office" in result.notification_text.lower()
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert vacancy.questions_context_json["current_question_key"] == "work_format"
    assert vacancy.questions_context_json["confirmed_fields"] == ["budget"]


def test_clarification_still_asks_project_and_stack_when_prefilled_from_summary() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)
    vacancy.project_description = "Prefilled from JD extraction."
    vacancy.primary_tech_stack_json = ["nodejs", "express", "redis"]
    fake_repo.update_questions_context(
        vacancy,
        {
            "follow_up_used": {
                "budget": False,
                "countries": False,
                "work_format": False,
                "team_size": False,
                "project_description": False,
                "primary_tech_stack": False,
            },
            "confirmed_fields": ["budget", "work_format", "countries"],
            "current_question_key": "team_size",
        },
    )

    result = service.handle_clarification_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={"team_size": 6},
    )

    assert result is not None
    assert result.status == "next_question"
    assert "english level" in result.notification_text.lower()
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert vacancy.questions_context_json["current_question_key"] == "english_level"
    assert vacancy.questions_context_json["confirmed_fields"] == [
        "budget",
        "countries",
        "team_size",
        "work_format",
    ]


def test_clarification_payload_filters_to_current_question_only() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)
    fake_repo.update_questions_context(
        vacancy,
        {
            "follow_up_used": {
                "budget": False,
                "countries": False,
                "work_format": False,
                "team_size": False,
                "project_description": False,
                "primary_tech_stack": False,
            },
            "confirmed_fields": ["budget", "work_format", "countries"],
            "current_question_key": "team_size",
        },
    )

    result = service.handle_clarification_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "team_size": 6,
            "project_description": "Payments platform for SMB clients.",
            "primary_tech_stack_json": ["nodejs", "redis"],
        },
    )

    assert result is not None
    assert result.status == "next_question"
    assert "english level" in result.notification_text.lower()
    assert vacancy.questions_context_json["current_question_key"] == "english_level"
    assert vacancy.team_size == 6
    assert vacancy.project_description is None
    assert vacancy.primary_tech_stack_json == []


def test_clarification_requires_office_city_for_hybrid_or_office() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)
    fake_repo.update_clarifications(
        vacancy,
        budget_min=7000,
        budget_currency="USD",
        budget_period="month",
    )
    fake_repo.update_questions_context(
        vacancy,
        {
            "follow_up_used": {
                "budget": False,
                "work_format": False,
                "office_city": False,
                "countries": False,
                "english_level": False,
                "assessment": False,
                "take_home_paid": False,
                "hiring_stages": False,
                "team_size": False,
                "project_description": False,
                "primary_tech_stack": False,
            },
            "confirmed_fields": ["budget"],
            "current_question_key": "work_format",
        },
    )

    result = service.handle_clarification_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={"work_format": "hybrid"},
    )

    assert result is not None
    assert result.status == "next_question"
    assert "city" in result.notification_text.lower()
    assert vacancy.questions_context_json["current_question_key"] == "office_city"


def test_clarification_requires_take_home_paid_when_take_home_enabled() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    vacancy = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_CLARIFICATION_QA)
    fake_repo.update_clarifications(
        vacancy,
        budget_min=7000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        countries_allowed_json=["PL"],
        required_english_level="B2",
        team_size=6,
        project_description="Payments platform.",
        primary_tech_stack_json=["python"],
    )
    fake_repo.update_questions_context(
        vacancy,
        {
            "follow_up_used": {
                "budget": False,
                "work_format": False,
                "office_city": False,
                "countries": False,
                "english_level": False,
                "assessment": False,
                "take_home_paid": False,
                "hiring_stages": False,
                "team_size": False,
                "project_description": False,
                "primary_tech_stack": False,
            },
            "confirmed_fields": [
                "budget",
                "work_format",
                "countries",
                "english_level",
                "team_size",
                "project_description",
                "primary_tech_stack",
            ],
            "current_question_key": "assessment",
        },
    )

    result = service.handle_clarification_parsed_payload(
        user=user,
        raw_message_id=uuid4(),
        parsed_payload={
            "has_take_home_task": True,
            "has_live_coding": False,
        },
    )

    assert result is not None
    assert result.status == "next_question"
    assert "paid or unpaid" in result.notification_text.lower()
    assert vacancy.questions_context_json["current_question_key"] == "take_home_paid"


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
    assert result.status == "next_question"
    assert vacancy.state == VACANCY_STATE_CLARIFICATION_QA
    assert vacancy.budget_min == 7000
    assert vacancy.questions_context_json["current_question_key"] == "work_format"


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

    first = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="delete_vacancy",
    )
    second = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="confirm_delete",
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


def test_execute_vacancy_deletion_action_confirm_soft_deletes_vacancy() -> None:
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

    first = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="delete_vacancy",
    )
    second = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="confirm_delete",
    )

    assert first is not None
    assert first.status == "confirmation_required"
    assert second is not None
    assert second.status == "deleted"
    assert vacancy.deleted_at == "now"
    assert vacancy.state == "DELETED"
    assert match.status == "cancelled"
    assert interview.state == "CANCELLED"


def test_execute_deletion_action_targets_named_open_vacancy() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.interviews = FakeInterviewsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    first = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_OPEN)
    first.role_title = "Android Developer"
    second = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_OPEN)
    second.role_title = "Node.js Developer"

    confirmation = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="delete_vacancy",
        latest_user_message="я хочу удалить вакансию андроид",
    )

    assert confirmation is not None
    assert confirmation.status == "confirmation_required"
    assert "Android Developer" in confirmation.notification_text

    deleted = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="confirm_delete",
        latest_user_message="Confirm delete vacancy",
    )

    assert deleted is not None
    assert deleted.status == "deleted"
    assert first.deleted_at == "now"
    assert second.deleted_at is None


def test_execute_deletion_action_can_delete_second_named_open_vacancy() -> None:
    service = VacancyService(FakeSession())
    fake_repo = FakeVacanciesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.matching = FakeMatchingRepository()
    service.interviews = FakeInterviewsRepository()
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    first = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_OPEN)
    first.role_title = "Node.js Developer"
    second = fake_repo.create(manager_user_id=user.id, state=VACANCY_STATE_OPEN)
    second.role_title = "Android Developer"

    confirmation = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="delete_vacancy",
        latest_user_message="я хочу удалить вакансию андроид",
    )

    assert confirmation is not None
    assert confirmation.status == "confirmation_required"
    assert "Android Developer" in confirmation.notification_text

    deleted = service.execute_deletion_action(
        user=user,
        raw_message_id=uuid4(),
        action="confirm_delete",
        latest_user_message="Delete vacancy",
    )

    assert deleted is not None
    assert deleted.status == "deleted"
    assert first.deleted_at is None
    assert second.deleted_at == "now"
