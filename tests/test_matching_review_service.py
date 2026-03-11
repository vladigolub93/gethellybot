from __future__ import annotations

from types import SimpleNamespace

from src.matching.policy import (
    MATCH_STATUS_APPROVED,
    MATCH_STATUS_CANDIDATE_APPLIED,
    MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    MATCH_STATUS_MANAGER_DECISION_PENDING,
    MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
)
from src.matching.review import MatchingReviewService


class FakeSession:
    pass


class FakeCandidateRepository:
    def __init__(self, *, candidate_by_id=None, active_candidate=None, versions=None):
        self.candidate_by_id = dict(candidate_by_id or {})
        self.active_candidate = active_candidate
        self.versions = dict(versions or {})

    def get_by_id(self, profile_id):
        return self.candidate_by_id.get(profile_id)

    def get_active_by_user_id(self, user_id):
        if self.active_candidate is not None and self.active_candidate.user_id == user_id:
            return self.active_candidate
        return None

    def get_version_by_id(self, version_id):
        return self.versions.get(version_id)


class FakeVerificationRepository:
    def get_latest_submitted_by_profile_id(self, profile_id):
        return None


class FakeEvaluationsRepository:
    def __init__(self):
        self.rows = []

    def create_introduction_event(self, **kwargs):
        row = SimpleNamespace(**kwargs)
        self.rows.append(row)
        return row


class FakeMatchingRepository:
    def __init__(
        self,
        *,
        shortlisted_for_vacancy=None,
        shortlisted_for_candidate=None,
        pre_vacancy=None,
        pre_candidate=None,
        active_candidate=None,
        active_vacancy=None,
    ):
        self.shortlisted_for_vacancy = list(shortlisted_for_vacancy or [])
        self.shortlisted_for_candidate = list(shortlisted_for_candidate or [])
        self.pre_vacancy = list(pre_vacancy or [])
        self.pre_candidate = list(pre_candidate or [])
        self.active_candidate = list(active_candidate or [])
        self.active_vacancy = list(active_vacancy or [])

    def list_shortlisted_for_vacancy(self, vacancy_id, *, limit=3):
        return list(self.shortlisted_for_vacancy)[:limit]

    def list_pre_interview_review_for_vacancy(self, vacancy_id, *, limit=3):
        return [match for match in self.pre_vacancy if match.vacancy_id == vacancy_id][:limit]

    def get_latest_pre_interview_review_for_manager(self, vacancy_ids):
        for match in self.pre_vacancy:
            if match.vacancy_id in vacancy_ids:
                return match
        return None

    def list_shortlisted_for_candidate(self, candidate_profile_id, *, limit=3):
        return [match for match in self.shortlisted_for_candidate if match.candidate_profile_id == candidate_profile_id][:limit]

    def list_pre_interview_review_for_candidate(self, candidate_profile_id, *, limit=3):
        return [match for match in self.pre_candidate if match.candidate_profile_id == candidate_profile_id][:limit]

    def get_latest_pre_interview_review_for_candidate(self, candidate_profile_id):
        for match in self.pre_candidate:
            if match.candidate_profile_id == candidate_profile_id:
                return match
        return None

    def list_active_for_candidate(self, candidate_profile_id):
        return [match for match in self.active_candidate if match.candidate_profile_id == candidate_profile_id]

    def list_active_for_vacancy(self, vacancy_id):
        return [match for match in self.active_vacancy if match.vacancy_id == vacancy_id]

    def get_by_id(self, match_id):
        for collection in (
            self.shortlisted_for_vacancy,
            self.shortlisted_for_candidate,
            self.pre_vacancy,
            self.pre_candidate,
            self.active_candidate,
            self.active_vacancy,
        ):
            for match in collection:
                if str(match.id) == str(match_id):
                    return match
        return None


class FakeNotificationsRepository:
    def __init__(self):
        self.rows = []

    def create(self, **kwargs):
        self.rows.append(SimpleNamespace(**kwargs))
        return self.rows[-1]


class FakeUsersRepository:
    def __init__(self, users):
        self.users = users

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class FakeVacanciesRepository:
    def __init__(self, *, vacancies, manager_vacancies=None, versions=None):
        self.vacancies = vacancies
        self.manager_vacancies = manager_vacancies or {}
        self.versions = versions or {}

    def get_by_id(self, vacancy_id):
        return self.vacancies.get(vacancy_id)

    def get_by_manager_user_id(self, manager_user_id):
        return list(self.manager_vacancies.get(manager_user_id, []))

    def get_version_by_id(self, version_id):
        return self.versions.get(version_id)


class FakeMessagingService:
    def compose(self, approved_intent: str) -> str:
        return approved_intent

    def compose_interview_invitation(self, *, role_title: str | None) -> str:
        return f"Interview invitation for {role_title or 'this role'}"


class FakeStateService:
    def __init__(self, matching_repo: FakeMatchingRepository):
        self.matching_repo = matching_repo
        self.transitions = []

    def transition(self, *, entity_type, entity, to_state, **kwargs):
        entity.status = to_state
        self.transitions.append({"entity_type": entity_type, "entity": entity, "to_state": to_state, **kwargs})
        if to_state == MATCH_STATUS_MANAGER_DECISION_PENDING and entity not in self.matching_repo.pre_vacancy:
            self.matching_repo.pre_vacancy.append(entity)
        if to_state == MATCH_STATUS_CANDIDATE_DECISION_PENDING and entity not in self.matching_repo.pre_candidate:
            self.matching_repo.pre_candidate.append(entity)
        if to_state == MATCH_STATUS_CANDIDATE_APPLIED and entity in self.matching_repo.pre_candidate:
            self.matching_repo.pre_candidate.remove(entity)
        return entity


def test_dispatch_manager_batch_for_vacancy_promotes_shortlisted_and_notifies(monkeypatch) -> None:
    monkeypatch.setattr("src.matching.review.build_candidate_package", lambda **kwargs: {"candidate_name": "Test Candidate"})
    monkeypatch.setattr(
        "src.matching.review.render_notification_text",
        lambda *, template_key, payload: f"Candidate package: {(payload.get('candidate_package') or {}).get('candidate_name')}",
    )

    vacancy = SimpleNamespace(id="vacancy-1", manager_user_id="manager-1", role_title="Senior Backend Engineer")
    candidate = SimpleNamespace(id="candidate-1", user_id="candidate-user-1")
    match = SimpleNamespace(
        id="match-1",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-1",
        status="shortlisted",
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={"cpv-1": SimpleNamespace(summary_json={"skills": ["python"]})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(shortlisted_for_vacancy=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Test Candidate"),
            vacancy.manager_user_id: SimpleNamespace(id=vacancy.manager_user_id, display_name="Manager"),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={vacancy.manager_user_id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_manager_batch_for_vacancy(vacancy_id=vacancy.id, force=False, trigger_type="job")

    assert result["status"] == "dispatched"
    assert match.status == MATCH_STATUS_MANAGER_DECISION_PENDING
    assert len(service.notifications.rows) == 1
    notification = service.notifications.rows[0]
    assert notification.user_id == vacancy.manager_user_id
    assert notification.template_key == "manager_pre_interview_review_ready"
    assert notification.payload_json["message_entries"][0]["text"].startswith("I found 1 candidate matches")
    assert notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Connect"
    assert notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][1]["text"] == "Skip"
    assert notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "mgr_pre:int:match-1"


def test_dispatch_candidate_batch_for_profile_promotes_shortlisted_and_notifies() -> None:
    candidate = SimpleNamespace(id="candidate-2", user_id="candidate-user-2")
    vacancy = SimpleNamespace(
        id="vacancy-2",
        role_title="Python Engineer",
        seniority_normalized="senior",
        budget_min=5000,
        budget_max=6500,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        countries_allowed_json=["PL", "UA"],
        primary_tech_stack_json=["python", "postgresql"],
        project_description="Own backend APIs and platform integrations.",
    )
    match = SimpleNamespace(
        id="match-2",
        vacancy_id=vacancy.id,
        vacancy_version_id="vacancy-version-2",
        candidate_profile_id=candidate.id,
        status="shortlisted",
        llm_rank_score=0.9,
        deterministic_score=0.8,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate})
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(shortlisted_for_candidate=[match], active_candidate=[])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Candidate")})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={
            "vacancy-version-2": SimpleNamespace(
                summary_json={
                    "approval_summary_text": "Own backend APIs and platform integrations for a Python product.",
                    "project_description_excerpt": "Modernize data and integration workflows.",
                }
            )
        },
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_candidate_batch_for_profile(candidate_profile_id=candidate.id, force=False, trigger_type="job")

    assert result["status"] == "dispatched"
    assert match.status == MATCH_STATUS_CANDIDATE_DECISION_PENDING
    assert len(service.notifications.rows) == 1
    notification = service.notifications.rows[0]
    assert notification.user_id == candidate.user_id
    assert notification.template_key == "candidate_vacancy_review_ready"
    assert notification.payload_json["message_entries"][0]["text"].startswith("I found 1 matching roles")
    assert "Vacancy package:" in notification.payload_json["message_entries"][1]["text"]
    assert "Role: Python Engineer" in notification.payload_json["message_entries"][1]["text"]
    assert (
        notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        == "cand_pre:apply:match-2"
    )
    assert (
        notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][1]["callback_data"]
        == "cand_pre:skip:match-2"
    )


def test_dispatch_manager_batch_for_vacancy_does_not_resend_existing_cards_on_force_refresh() -> None:
    vacancy = SimpleNamespace(id="vacancy-force-1", manager_user_id="manager-force-1", role_title="Node.js Developer")
    existing_match = SimpleNamespace(
        id="match-existing",
        vacancy_id=vacancy.id,
        candidate_profile_id="candidate-existing",
        candidate_profile_version_id="cpv-existing",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={"candidate-existing": SimpleNamespace(id="candidate-existing", user_id="candidate-user-existing")},
        versions={"cpv-existing": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[existing_match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            "candidate-user-existing": SimpleNamespace(id="candidate-user-existing", display_name="Existing Candidate"),
            vacancy.manager_user_id: SimpleNamespace(id=vacancy.manager_user_id, display_name="Manager"),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={vacancy.manager_user_id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_manager_batch_for_vacancy(vacancy_id=vacancy.id, force=True, trigger_type="job")

    assert result["status"] == "already_presented"
    assert result["batch_count"] == 1
    assert service.notifications.rows == []


def test_dispatch_manager_batch_for_vacancy_sends_only_new_cards_on_force_refresh() -> None:
    vacancy = SimpleNamespace(id="vacancy-force-2", manager_user_id="manager-force-2", role_title="Node.js Developer")
    existing_candidate = SimpleNamespace(id="candidate-existing-2", user_id="candidate-user-existing-2")
    new_candidate = SimpleNamespace(id="candidate-new-2", user_id="candidate-user-new-2")
    existing_match = SimpleNamespace(
        id="match-existing-2",
        vacancy_id=vacancy.id,
        candidate_profile_id=existing_candidate.id,
        candidate_profile_version_id="cpv-existing-2",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
    )
    new_match = SimpleNamespace(
        id="match-new-2",
        vacancy_id=vacancy.id,
        candidate_profile_id=new_candidate.id,
        candidate_profile_version_id="cpv-new-2",
        status="shortlisted",
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={
            existing_candidate.id: existing_candidate,
            new_candidate.id: new_candidate,
        },
        versions={
            "cpv-existing-2": SimpleNamespace(summary_json={}),
            "cpv-new-2": SimpleNamespace(summary_json={}),
        },
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[existing_match], shortlisted_for_vacancy=[new_match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            existing_candidate.user_id: SimpleNamespace(id=existing_candidate.user_id, display_name="Existing Candidate"),
            new_candidate.user_id: SimpleNamespace(id=new_candidate.user_id, display_name="New Candidate"),
            vacancy.manager_user_id: SimpleNamespace(id=vacancy.manager_user_id, display_name="Manager"),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={vacancy.manager_user_id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_manager_batch_for_vacancy(vacancy_id=vacancy.id, force=True, trigger_type="job")

    assert result["status"] == "dispatched"
    assert result["batch_count"] == 2
    assert result["notified_count"] == 1
    assert result["promoted_count"] == 1
    assert len(service.notifications.rows) == 1
    entries = service.notifications.rows[0].payload_json["message_entries"]
    assert entries[0]["text"].startswith("I found 1 candidate matches")
    assert len(entries) == 2
    assert entries[1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "mgr_pre:int:match-new-2"


def test_dispatch_candidate_batch_for_profile_does_not_resend_existing_cards_on_force_refresh() -> None:
    candidate = SimpleNamespace(id="candidate-force-1", user_id="candidate-user-force-1")
    vacancy = SimpleNamespace(id="vacancy-force-cand-1", role_title="Python Engineer")
    existing_match = SimpleNamespace(
        id="match-force-cand-1",
        vacancy_id=vacancy.id,
        vacancy_version_id="vacancy-version-force-cand-1",
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate})
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[existing_match], active_candidate=[])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Candidate")})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={"vacancy-version-force-cand-1": SimpleNamespace(summary_json={})},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_candidate_batch_for_profile(candidate_profile_id=candidate.id, force=True, trigger_type="job")

    assert result["status"] == "already_presented"
    assert result["batch_count"] == 1
    assert service.notifications.rows == []


def test_execute_candidate_pre_interview_action_accepts_match_id_from_inline_button() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-inline", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-inline", user_id=candidate_user.id)
    vacancy = SimpleNamespace(id="vacancy-inline", role_title="Platform Engineer")
    match = SimpleNamespace(
        id="match-inline",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match], active_candidate=[])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(vacancies={vacancy.id: vacancy})
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_candidate_pre_interview_action(
        user=candidate_user,
        raw_message_id="raw-inline-candidate",
        action="apply_to_vacancy",
        vacancy_slot=None,
        match_id=match.id,
    )

    assert result is not None
    assert result.status == "applied"
    assert match.status == MATCH_STATUS_CANDIDATE_APPLIED


def test_dispatch_manager_batch_for_vacancy_reports_cap_reached() -> None:
    vacancy = SimpleNamespace(id="vacancy-cap", manager_user_id="manager-cap", role_title="Principal Engineer")
    active_pipeline = [
        SimpleNamespace(id=f"active-{index}", vacancy_id=vacancy.id, status=MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED)
        for index in range(10)
    ]

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository()
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(active_vacancy=active_pipeline)
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({vacancy.manager_user_id: SimpleNamespace(id=vacancy.manager_user_id)})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={vacancy.manager_user_id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_manager_batch_for_vacancy(vacancy_id=vacancy.id, force=True, trigger_type="job")

    assert result["status"] == "vacancy_cap_reached"
    assert len(service.notifications.rows) == 1
    text = service.notifications.rows[0].payload_json["text"].lower()
    assert "vacancy pipeline" in text
    assert "active decisions" in text


def test_execute_candidate_pre_interview_action_applies_and_notifies_manager() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-3", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-3", user_id=candidate_user.id)
    vacancy = SimpleNamespace(id="vacancy-3", manager_user_id="manager-3", role_title="Staff Engineer")
    match = SimpleNamespace(
        id="match-3",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        llm_rank_score=0.7,
        deterministic_score=0.6,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        active_candidate=candidate,
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match], active_candidate=[])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate_user.id: candidate_user,
            vacancy.manager_user_id: SimpleNamespace(id=vacancy.manager_user_id, is_candidate=False, is_hiring_manager=True),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={vacancy.manager_user_id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    manager_dispatch_calls = []
    candidate_batch_calls = []
    service.dispatch_manager_batch_for_vacancy = lambda **kwargs: manager_dispatch_calls.append(kwargs) or {
        "status": "dispatched",
        "batch_count": 1,
        "notified": True,
    }
    service.dispatch_candidate_batch_for_profile = lambda **kwargs: candidate_batch_calls.append(kwargs) or {
        "status": "empty",
        "batch_count": 0,
        "notified": False,
    }

    result = service.execute_candidate_pre_interview_action(
        user=candidate_user,
        raw_message_id="raw-1",
        action="apply_to_vacancy",
        vacancy_slot=1,
    )

    assert result is not None
    assert result.status == "applied"
    assert match.status == MATCH_STATUS_CANDIDATE_APPLIED
    assert manager_dispatch_calls == [
        {"vacancy_id": vacancy.id, "force": True, "trigger_type": "user_action"}
    ]
    assert candidate_batch_calls == [
        {"candidate_profile_id": candidate.id, "force": True, "trigger_type": "user_action"}
    ]
    assert len(service.notifications.rows) == 2
    assert "Applied to Staff Engineer" in service.notifications.rows[0].payload_json["text"]


def test_execute_manager_pre_interview_action_accepts_match_id_from_inline_button() -> None:
    manager_user = SimpleNamespace(id="manager-inline", is_hiring_manager=True, is_candidate=False)
    candidate = SimpleNamespace(id="candidate-inline", user_id="candidate-user-inline")
    vacancy = SimpleNamespace(id="vacancy-inline", manager_user_id=manager_user.id, role_title="Node.js Developer")
    match = SimpleNamespace(
        id="match-inline",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-inline",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={"cpv-inline": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[match], active_vacancy=[])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Inline Candidate"),
            manager_user.id: SimpleNamespace(id=manager_user.id),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={manager_user.id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_manager_pre_interview_action(
        user=manager_user,
        raw_message_id="raw-inline",
        action="interview_candidate",
        candidate_slot=None,
        match_id=match.id,
    )

    assert result.status == "awaiting_candidate"
    assert match.status == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED
    candidate_notification = service.notifications.rows[0]
    assert candidate_notification.template_key == "candidate_vacancy_review_ready"
    assert candidate_notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Connect"
    assert candidate_notification.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][1]["text"] == "Skip"
    assert "Vacancy package:" in candidate_notification.payload_json["message_entries"][1]["text"]


def test_execute_manager_pre_interview_skip_notifies_candidate_after_apply() -> None:
    manager_user = SimpleNamespace(id="manager-4", is_candidate=False, is_hiring_manager=True)
    candidate = SimpleNamespace(id="candidate-4", user_id="candidate-user-4")
    vacancy = SimpleNamespace(id="vacancy-4", manager_user_id=manager_user.id, role_title="Platform Engineer")
    match = SimpleNamespace(
        id="match-4",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_CANDIDATE_APPLIED,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate})
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Candidate"),
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={manager_user.id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)
    service.dispatch_manager_batch_for_vacancy = lambda **kwargs: {
        "status": "empty",
        "batch_count": 0,
        "notified": False,
    }

    result = service.execute_manager_pre_interview_action(
        user=manager_user,
        raw_message_id="raw-manager-1",
        action="skip_candidate",
        candidate_slot=1,
    )

    assert result is not None
    assert result.status == "skipped"
    assert len(service.notifications.rows) == 3
    assert service.notifications.rows[1].user_id == candidate.user_id
    assert "not to move forward" in service.notifications.rows[1].payload_json["text"].lower()


def test_execute_candidate_pre_interview_apply_is_blocked_when_candidate_cap_reached() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-cap", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-cap", user_id=candidate_user.id)
    vacancy = SimpleNamespace(id="vacancy-cap-2", manager_user_id="manager-cap-2", role_title="Backend Engineer")
    pending_match = SimpleNamespace(
        id="match-cap-pending",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    )
    active_matches = [
        SimpleNamespace(
            id=f"active-candidate-{index}",
            vacancy_id=f"vacancy-active-{index}",
            candidate_profile_id=candidate.id,
            status=MATCH_STATUS_CANDIDATE_APPLIED,
        )
        for index in range(10)
    ]

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[pending_match], active_candidate=active_matches)
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(vacancies={vacancy.id: vacancy})
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_candidate_pre_interview_action(
        user=candidate_user,
        raw_message_id="raw-cap-1",
        action="apply_to_vacancy",
        vacancy_slot=1,
    )

    assert result is not None
    assert result.status == "applied"
    assert pending_match.status == MATCH_STATUS_CANDIDATE_APPLIED
    assert "active opportunities in progress" in service.notifications.rows[-1].payload_json["text"].lower()


def test_execute_manager_pre_interview_invite_is_blocked_when_vacancy_cap_reached() -> None:
    manager_user = SimpleNamespace(id="manager-user-cap", is_candidate=False, is_hiring_manager=True)
    candidate = SimpleNamespace(id="candidate-manager-cap", user_id="candidate-user-manager-cap")
    vacancy = SimpleNamespace(id="vacancy-manager-cap", manager_user_id=manager_user.id, role_title="Staff Engineer")
    pending_match = SimpleNamespace(
        id="match-manager-cap",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
    )
    active_pipeline = [
        SimpleNamespace(id=f"active-{index}", vacancy_id=vacancy.id, status=MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED)
        for index in range(10)
    ]

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate})
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[pending_match], active_vacancy=active_pipeline)
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Candidate"),
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={manager_user.id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_manager_pre_interview_action(
        user=manager_user,
        raw_message_id="raw-manager-cap",
        action="interview_candidate",
        candidate_slot=1,
    )

    assert result is not None
    assert result.status == "vacancy_cap_reached"
    assert pending_match.status == MATCH_STATUS_MANAGER_DECISION_PENDING
    text = service.notifications.rows[0].payload_json["text"].lower()
    assert "active on this vacancy" in text
    assert "active decisions" in text


def test_execute_manager_pre_interview_action_shares_contacts_immediately_when_candidate_already_applied() -> None:
    manager_user = SimpleNamespace(
        id="manager-connect",
        is_hiring_manager=True,
        is_candidate=False,
        display_name="Manager",
        username="manager_connect",
        phone_number="+380111111111",
    )
    candidate = SimpleNamespace(id="candidate-connect", user_id="candidate-user-connect")
    vacancy = SimpleNamespace(id="vacancy-connect", manager_user_id=manager_user.id, role_title="Node.js Developer")
    match = SimpleNamespace(
        id="match-connect",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-connect",
        status=MATCH_STATUS_CANDIDATE_APPLIED,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={"cpv-connect": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[match], active_vacancy=[])
    service.notifications = FakeNotificationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(
                id=candidate.user_id,
                display_name="Applied Candidate",
                username="applied_candidate",
                phone_number="+380222222222",
            ),
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={manager_user.id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_manager_pre_interview_action(
        user=manager_user,
        raw_message_id="raw-manager-connect",
        action="interview_candidate",
        candidate_slot=None,
        match_id=match.id,
    )

    assert result.status == "approved"
    assert match.status == MATCH_STATUS_APPROVED
    assert len(service.evaluations.rows) == 1
    assert len(service.notifications.rows) == 2
    assert service.notifications.rows[0].template_key == "candidate_approved_introduction"
    assert service.notifications.rows[1].template_key == "manager_candidate_approved"


def test_execute_candidate_pre_interview_action_shares_contacts_immediately_when_manager_already_approved() -> None:
    candidate_user = SimpleNamespace(
        id="candidate-user-approved",
        is_candidate=True,
        is_hiring_manager=False,
        display_name="Candidate",
        username="candidate_connect",
        phone_number="+380333333333",
    )
    candidate = SimpleNamespace(id="candidate-approved", user_id=candidate_user.id)
    manager_user = SimpleNamespace(
        id="manager-approved",
        display_name="Manager",
        username="manager_approved",
        phone_number="+380444444444",
    )
    vacancy = SimpleNamespace(id="vacancy-approved", manager_user_id=manager_user.id, role_title="Backend Engineer")
    match = SimpleNamespace(
        id="match-approved",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match], active_candidate=[])
    service.notifications = FakeNotificationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate_user.id: candidate_user,
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(vacancies={vacancy.id: vacancy})
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_candidate_pre_interview_action(
        user=candidate_user,
        raw_message_id="raw-candidate-connect",
        action="apply_to_vacancy",
        vacancy_slot=None,
        match_id=match.id,
    )

    assert result.status == "approved"
    assert match.status == MATCH_STATUS_APPROVED
    assert len(service.evaluations.rows) == 1
    assert len(service.notifications.rows) == 2
    assert service.notifications.rows[0].template_key == "candidate_approved_introduction"
    assert service.notifications.rows[1].template_key == "manager_candidate_approved"
