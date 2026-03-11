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
    def __init__(self, match, extra_matches=None):
        self.match = match
        self.matches = [match] + list(extra_matches or [])

    def get_by_id(self, match_id):
        for match in self.matches:
            if str(match.id) == str(match_id):
                return match
        return None

    def mark_manager_decision(self, match, *, status):
        match.status = status
        match.manager_decision_at = "now"
        return match

    def get_latest_manager_review_for_manager(self, vacancy_ids, manager_review_only=True):
        for match in reversed(self.matches):
            if match.vacancy_id in vacancy_ids and match.status == "manager_review":
                return match
        return None

    def list_manager_review_for_manager(self, vacancy_ids, *, limit=3):
        rows = [
            match
            for match in reversed(self.matches)
            if match.vacancy_id in vacancy_ids and match.status == "manager_review"
        ]
        return rows[:limit]


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
    def __init__(self, manager, candidate_user):
        self.manager = manager
        self.candidate_user = candidate_user

    def get_by_id(self, user_id):
        if self.manager.id == user_id:
            return self.manager
        if self.candidate_user.id == user_id:
            return self.candidate_user
        return None


class FakeCandidateVerificationsRepository:
    def __init__(self, verification):
        self.verification = verification

    def get_latest_submitted_by_profile_id(self, profile_id):
        if self.verification and self.verification.profile_id == profile_id:
            return self.verification
        return None


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
    candidate_user = SimpleNamespace(id=uuid4(), display_name="Candidate User", username="candidateuser", phone_number="+111111")
    candidate = SimpleNamespace(id=uuid4(), user_id=candidate_user.id, state="READY", location_text="Warsaw", work_format="remote", salary_min=4000, salary_currency="USD", salary_period="month")
    manager = SimpleNamespace(id=uuid4(), is_hiring_manager=True, display_name="Manager User", username="manageruser", phone_number="+222222")
    candidate_version = SimpleNamespace(id=uuid4(), summary_json={"skills": ["python", "postgresql"], "years_experience": 6})
    vacancy = SimpleNamespace(id=uuid4(), manager_user_id=manager.id, role_title="Senior Python Engineer", primary_tech_stack_json=["python", "postgresql"])
    verification = SimpleNamespace(id=uuid4(), profile_id=candidate.id, status="submitted")
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
    service.verifications = FakeCandidateVerificationsRepository(verification)
    service.vacancies = FakeVacancyRepository(vacancy)
    service.interviews = FakeInterviewsRepository(session_row, answers)
    service.matches = FakeMatchingRepository(match)
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(manager, candidate_user)
    service.state_service = FakeStateService()
    return service, candidate, candidate_user, manager, match, session_row


def test_evaluate_interview_routes_candidate_to_manager_review() -> None:
    service, candidate, _candidate_user, manager, match, session_row = _build_service()

    result = service.evaluate_interview(interview_session_id=session_row.id)

    assert result["status"] == "manager_review"
    assert match.status == "manager_review"
    assert candidate.state == "READY"
    assert len(service.notifications.rows) == 1
    assert service.notifications.rows[0].user_id == manager.id
    candidate_package = service.notifications.rows[0].payload_json["candidate_package"]
    message_entries = service.notifications.rows[0].payload_json["message_entries"]
    assert candidate_package["candidate_name"] == "Candidate User"
    assert candidate_package["verification_status"] == "verification_submitted"
    assert candidate_package["recommendation"] == "advance"
    assert "final decision is yours" in service.notifications.rows[0].payload_json["text"].lower()
    assert message_entries[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"mgr_rev:approve:{match.id}"
    assert message_entries[-1]["reply_markup"]["inline_keyboard"][0][1]["callback_data"] == f"mgr_rev:reject:{match.id}"


def test_evaluate_interview_with_reject_recommendation_still_routes_to_manager_review(monkeypatch) -> None:
    service, candidate, _candidate_user, manager, match, session_row = _build_service()

    monkeypatch.setattr(
        "src.evaluation.service.safe_evaluate_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(
            payload={
                "final_score": 0.22,
                "strengths": ["Candidate answered the questions."],
                "risks": ["Stack fit is weak."],
                "recommendation": "reject",
                "interview_summary": "Candidate has relevant experience, but the role fit looks weak overall.",
            }
        ),
    )

    result = service.evaluate_interview(interview_session_id=session_row.id)

    assert result["status"] == "manager_review"
    assert match.status == "manager_review"
    assert candidate.state == "READY"
    assert len(service.notifications.rows) == 1
    assert service.notifications.rows[0].user_id == manager.id
    candidate_package = service.notifications.rows[0].payload_json["candidate_package"]
    assert candidate_package["recommendation"] == "reject"
    assert candidate_package["interview_summary"].startswith("Candidate has relevant experience")
    assert candidate.state == "READY"


def test_manager_approve_creates_introduction_event() -> None:
    service, candidate, _candidate_user, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.execute_manager_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_candidate",
    )

    assert result is not None
    assert result.status == "approved"
    assert match.status == "approved"
    assert candidate.state == "READY"
    assert len(service.evaluations.introductions) == 1
    assert len(service.notifications.rows) == 2
    candidate_notification = service.notifications.rows[0]
    manager_notification = service.notifications.rows[1]
    assert candidate_notification.payload_json["counterparty"]["username"] == "manageruser"
    assert manager_notification.payload_json["counterparty"]["username"] == "candidateuser"


def test_manager_reject_updates_match_and_candidate() -> None:
    service, candidate, _candidate_user, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.execute_manager_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="reject_candidate",
    )

    assert result is not None
    assert result.status == "rejected"
    assert match.status == "rejected"
    assert candidate.state == "READY"
    assert len(service.notifications.rows) == 2
    assert service.notifications.rows[0].user_id == candidate.user_id
    assert "did not move forward" in service.notifications.rows[0].payload_json["text"].lower()
    assert service.notifications.rows[1].user_id == manager.id


def test_execute_manager_review_action_approves_without_raw_text_parsing() -> None:
    service, candidate, _candidate_user, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.execute_manager_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_candidate",
    )

    assert result is not None
    assert result.status == "approved"
    assert match.status == "approved"


def test_execute_manager_review_action_uses_explicit_match_id() -> None:
    service, candidate, _candidate_user, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.execute_manager_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_candidate",
        match_id=str(match.id),
    )

    assert result is not None
    assert result.status == "approved"
    assert match.status == "approved"
    assert candidate.state == "READY"


def test_execute_manager_review_action_rejects_unknown_match_id() -> None:
    service, candidate, _candidate_user, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.execute_manager_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_candidate",
        match_id=str(uuid4()),
    )

    assert result is None
    assert match.status == "manager_review"
    assert candidate.state == "READY"


def test_execute_manager_review_action_requires_buttons_when_multiple_reviews_exist() -> None:
    service, candidate, _candidate_user, manager, match, _session_row = _build_service()
    match.status = "manager_review"
    second_match = SimpleNamespace(
        id=uuid4(),
        vacancy_id=match.vacancy_id,
        candidate_profile_id=match.candidate_profile_id,
        candidate_profile_version_id=match.candidate_profile_version_id,
        status="manager_review",
        manager_decision_at=None,
    )
    service.matches = FakeMatchingRepository(match, extra_matches=[second_match])
    user = SimpleNamespace(id=manager.id, is_hiring_manager=True)

    result = service.execute_manager_review_action(
        user=user,
        raw_message_id=uuid4(),
        action="approve_candidate",
    )

    assert result is not None
    assert result.status == "help"
    assert "more than one candidate waiting for final review" in result.notification_text.lower()
    assert match.status == "manager_review"
    assert second_match.status == "manager_review"
