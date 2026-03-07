from types import SimpleNamespace
from uuid import uuid4

from src.evaluation.service import EvaluationService


class FakeSession:
    pass


class FakeCandidateRepository:
    def __init__(self, candidate, candidate_version):
        self.candidate = candidate
        self.candidate_version = candidate_version

    def get_by_id(self, candidate_profile_id):
        return self.candidate if self.candidate.id == candidate_profile_id else None

    def get_version_by_id(self, version_id):
        return self.candidate_version if self.candidate_version.id == version_id else None


class FakeVacancyRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_by_id(self, vacancy_id):
        return self.vacancy if self.vacancy.id == vacancy_id else None

    def get_by_manager_user_id(self, manager_user_id):
        return [self.vacancy] if self.vacancy.manager_user_id == manager_user_id else []


class FakeInterviewsRepository:
    def __init__(self, session_row, answers):
        self.session_row = session_row
        self.answers = answers

    def get_by_id(self, session_id):
        return self.session_row if self.session_row.id == session_id else None

    def list_answers_for_session(self, session_id):
        return self.answers if self.session_row.id == session_id else []


class FakeMatchingRepository:
    def __init__(self, match):
        self.match = match

    def get_by_id(self, match_id):
        return self.match if self.match.id == match_id else None

    def mark_manager_decision(self, match, *, status):
        match.status = status
        match.manager_decision_at = "now"
        return match

    def get_latest_manager_review_for_manager(self, vacancy_ids, manager_review_only=True):
        if self.match.vacancy_id in vacancy_ids and self.match.status == "manager_review":
            return self.match
        return None


class FakeEvaluationsRepository:
    def __init__(self):
        self.rows = []
        self.introductions = []

    def create(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row

    def create_introduction_event(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.introductions.append(row)
        return row


class FakeNotificationsRepository:
    def __init__(self):
        self.rows = []

    def create(self, **kwargs):
        self.rows.append(SimpleNamespace(**kwargs))
        return self.rows[-1]


class FakeUsersRepository:
    def __init__(self, manager):
        self.manager = manager

    def get_by_id(self, user_id):
        return self.manager if self.manager.id == user_id else None


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


def _build_service():
    candidate = SimpleNamespace(id=uuid4(), user_id=uuid4(), state="READY")
    manager = SimpleNamespace(id=uuid4(), is_hiring_manager=True)
    candidate_version = SimpleNamespace(id=uuid4(), summary_json={"skills": ["python", "postgresql"], "years_experience": 6})
    vacancy = SimpleNamespace(id=uuid4(), manager_user_id=manager.id, role_title="Senior Python Engineer", primary_tech_stack_json=["python", "postgresql"])
    match = SimpleNamespace(
        id=uuid4(),
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id=candidate_version.id,
        status="interview_completed",
        manager_decision_at=None,
    )
    session_row = SimpleNamespace(id=uuid4(), match_id=match.id, candidate_profile_id=candidate.id, vacancy_id=vacancy.id, state="COMPLETED")
    answers = [SimpleNamespace(answer_text=f"Answer {index}") for index in range(5)]

    service = EvaluationService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate, candidate_version)
    service.vacancies = FakeVacancyRepository(vacancy)
    service.interviews = FakeInterviewsRepository(session_row, answers)
    service.matches = FakeMatchingRepository(match)
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(manager)
    service.state_service = FakeStateService()
    return service, candidate, manager, match, session_row


def test_evaluate_interview_routes_candidate_to_manager_review() -> None:
    service, candidate, manager, match, session_row = _build_service()

    result = service.evaluate_interview(interview_session_id=session_row.id)

    assert result["status"] == "manager_review"
    assert match.status == "manager_review"
    assert candidate.state == "UNDER_MANAGER_REVIEW"
    assert len(service.notifications.rows) == 1
    assert service.notifications.rows[0].user_id == manager.id


def test_manager_approve_creates_introduction_event() -> None:
    service, candidate, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.handle_manager_message(
        user=user,
        raw_message_id=uuid4(),
        text="Approve candidate",
    )

    assert result is not None
    assert result.status == "approved"
    assert match.status == "approved"
    assert candidate.state == "APPROVED"
    assert len(service.evaluations.introductions) == 1


def test_manager_reject_updates_match_and_candidate() -> None:
    service, candidate, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.handle_manager_message(
        user=user,
        raw_message_id=uuid4(),
        text="Reject candidate",
    )

    assert result is not None
    assert result.status == "rejected"
    assert match.status == "rejected"
    assert candidate.state == "REJECTED"
