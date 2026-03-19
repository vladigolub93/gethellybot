from __future__ import annotations

from types import SimpleNamespace

from src.matching.policy import (
    MATCH_STATUS_APPROVED,
    MATCH_STATUS_CANDIDATE_APPLIED,
    MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    MATCH_STATUS_MANAGER_DECISION_PENDING,
    MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
    MATCH_STATUS_MANAGER_SKIPPED,
    PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES,
    PRE_INTERVIEW_MANAGER_REVIEW_STATUSES,
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

    def get_current_version(self, candidate):
        return self.versions.get(getattr(candidate, "current_version_id", None))

    def update_questions_context(self, candidate, questions_context_json):
        candidate.questions_context_json = questions_context_json
        return candidate


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
        return [
            match
            for match in self.pre_vacancy
            if match.vacancy_id == vacancy_id and getattr(match, "status", None) in PRE_INTERVIEW_MANAGER_REVIEW_STATUSES
        ][:limit]

    def get_latest_pre_interview_review_for_manager(self, vacancy_ids):
        for match in self.pre_vacancy:
            if (
                match.vacancy_id in vacancy_ids
                and getattr(match, "status", None) in PRE_INTERVIEW_MANAGER_REVIEW_STATUSES
            ):
                return match
        return None

    def list_shortlisted_for_candidate(self, candidate_profile_id, *, limit=3):
        return [match for match in self.shortlisted_for_candidate if match.candidate_profile_id == candidate_profile_id][:limit]

    def list_pre_interview_review_for_candidate(self, candidate_profile_id, *, limit=3):
        return [
            match
            for match in self.pre_candidate
            if getattr(match, "candidate_profile_id", None) == candidate_profile_id
            and getattr(match, "status", None) in PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES
        ][:limit]

    def get_latest_pre_interview_review_for_candidate(self, candidate_profile_id):
        for match in self.pre_candidate:
            if (
                match.candidate_profile_id == candidate_profile_id
                and getattr(match, "status", None) in PRE_INTERVIEW_CANDIDATE_REVIEW_STATUSES
            ):
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

    def get_current_version(self, vacancy):
        return self.versions.get(getattr(vacancy, "current_version_id", None))

    def update_questions_context(self, vacancy, questions_context_json):
        vacancy.questions_context_json = questions_context_json
        return vacancy


class FakeMessagingService:
    def compose(self, approved_intent: str) -> str:
        return approved_intent

    def compose_match_card(self, **kwargs) -> str:
        return kwargs.get("fallback_message", "")

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


def test_dispatch_manager_batch_for_vacancy_promotes_shortlisted_and_notifies() -> None:
    vacancy = SimpleNamespace(id="vacancy-1", manager_user_id="manager-1", role_title="Senior Backend Engineer")
    candidate = SimpleNamespace(id="candidate-1", user_id="candidate-user-1")
    match = SimpleNamespace(
        id="match-1",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-1",
        status="shortlisted",
        rationale_json={"fit_band": "strong", "gap_signals": []},
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
    assert notification.payload_json["message_entries"][0]["text"].startswith("I found a strong-fit candidate")
    assert notification.payload_json["message_entries"][1]["text"].startswith("I found you Test Candidate for the Senior Backend Engineer role.")
    assert "This looks like a strong fit." in notification.payload_json["message_entries"][1]["text"]
    assert "Use Connect or Skip below." in notification.payload_json["message_entries"][1]["text"]
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
    assert notification.payload_json["message_entries"][0]["text"].startswith("I found a role worth reviewing")
    assert notification.payload_json["message_entries"][1]["text"].startswith("I found you a vacancy for Python Engineer.")
    assert "The client is offering 5000-6500 USD / month in a remote setup." in notification.payload_json["message_entries"][1]["text"]
    assert "Use Apply or Skip below." in notification.payload_json["message_entries"][1]["text"]
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


def test_dispatch_manager_batch_for_vacancy_keeps_single_current_card_on_force_refresh() -> None:
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
        rationale_json={"fit_band": "strong", "gap_signals": []},
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

    assert result["status"] == "already_presented"
    assert result["batch_count"] == 1
    assert result["promoted_count"] == 0
    assert len(service.notifications.rows) == 0
    assert new_match.status == "shortlisted"


def test_dispatch_manager_batch_for_vacancy_prefers_strong_fit_candidates_first() -> None:
    vacancy = SimpleNamespace(id="vacancy-fit-1", manager_user_id="manager-fit-1", role_title="Node.js Developer")
    strong_candidate = SimpleNamespace(id="candidate-strong", user_id="candidate-user-strong")
    medium_candidate = SimpleNamespace(id="candidate-medium", user_id="candidate-user-medium")
    low_candidate = SimpleNamespace(id="candidate-low", user_id="candidate-user-low")
    strong_match = SimpleNamespace(
        id="match-strong",
        vacancy_id=vacancy.id,
        candidate_profile_id=strong_candidate.id,
        candidate_profile_version_id="cpv-strong",
        status="shortlisted",
        rationale_json={"fit_band": "strong", "gap_signals": []},
        llm_rank_position=2,
        llm_rank_score=0.82,
        deterministic_score=0.83,
    )
    medium_match = SimpleNamespace(
        id="match-medium",
        vacancy_id=vacancy.id,
        candidate_profile_id=medium_candidate.id,
        candidate_profile_version_id="cpv-medium",
        status="shortlisted",
        rationale_json={"fit_band": "medium", "gap_signals": ["Core stack overlap is partial."]},
        llm_rank_position=1,
        llm_rank_score=0.91,
        deterministic_score=0.79,
    )
    low_match = SimpleNamespace(
        id="match-low",
        vacancy_id=vacancy.id,
        candidate_profile_id=low_candidate.id,
        candidate_profile_version_id="cpv-low",
        status="shortlisted",
        rationale_json={"fit_band": "low", "gap_signals": ["Role alignment is not exact."]},
        llm_rank_position=1,
        llm_rank_score=0.95,
        deterministic_score=0.7,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={
            strong_candidate.id: strong_candidate,
            medium_candidate.id: medium_candidate,
            low_candidate.id: low_candidate,
        },
        versions={
            "cpv-strong": SimpleNamespace(summary_json={}),
            "cpv-medium": SimpleNamespace(summary_json={}),
            "cpv-low": SimpleNamespace(summary_json={}),
        },
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(
        shortlisted_for_vacancy=[low_match, medium_match, strong_match],
    )
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            strong_candidate.user_id: SimpleNamespace(id=strong_candidate.user_id, display_name="Strong Candidate"),
            medium_candidate.user_id: SimpleNamespace(id=medium_candidate.user_id, display_name="Medium Candidate"),
            low_candidate.user_id: SimpleNamespace(id=low_candidate.user_id, display_name="Low Candidate"),
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
    assert result["fit_band"] == "strong"
    assert result["batch_count"] == 1
    assert strong_match.status == MATCH_STATUS_MANAGER_DECISION_PENDING
    assert medium_match.status == "shortlisted"
    assert low_match.status == "shortlisted"


def test_dispatch_manager_batch_for_vacancy_does_not_mix_lower_fit_band_into_existing_batch() -> None:
    vacancy = SimpleNamespace(id="vacancy-fit-2", manager_user_id="manager-fit-2", role_title="Node.js Developer")
    strong_candidate = SimpleNamespace(id="candidate-strong-2", user_id="candidate-user-strong-2")
    medium_candidate = SimpleNamespace(id="candidate-medium-2", user_id="candidate-user-medium-2")
    existing_match = SimpleNamespace(
        id="match-existing-strong",
        vacancy_id=vacancy.id,
        candidate_profile_id=strong_candidate.id,
        candidate_profile_version_id="cpv-existing-strong",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "gap_signals": []},
    )
    medium_match = SimpleNamespace(
        id="match-medium-2",
        vacancy_id=vacancy.id,
        candidate_profile_id=medium_candidate.id,
        candidate_profile_version_id="cpv-medium-2",
        status="shortlisted",
        rationale_json={"fit_band": "medium", "gap_signals": ["Core stack overlap is partial."]},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={
            strong_candidate.id: strong_candidate,
            medium_candidate.id: medium_candidate,
        },
        versions={
            "cpv-existing-strong": SimpleNamespace(summary_json={}),
            "cpv-medium-2": SimpleNamespace(summary_json={}),
        },
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(
        pre_vacancy=[existing_match],
        shortlisted_for_vacancy=[medium_match],
    )
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            strong_candidate.user_id: SimpleNamespace(id=strong_candidate.user_id, display_name="Strong Candidate"),
            medium_candidate.user_id: SimpleNamespace(id=medium_candidate.user_id, display_name="Medium Candidate"),
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
    assert medium_match.status == "shortlisted"
    assert service.notifications.rows == []


def test_dispatch_manager_batch_for_vacancy_moves_to_medium_fit_when_no_strong_left() -> None:
    vacancy = SimpleNamespace(id="vacancy-fit-3", manager_user_id="manager-fit-3", role_title="Node.js Developer")
    medium_candidate = SimpleNamespace(id="candidate-medium-3", user_id="candidate-user-medium-3")
    medium_match = SimpleNamespace(
        id="match-medium-3",
        vacancy_id=vacancy.id,
        candidate_profile_id=medium_candidate.id,
        candidate_profile_version_id="cpv-medium-3",
        status="shortlisted",
        rationale_json={"fit_band": "medium", "gap_signals": ["Core stack overlap is partial."]},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={medium_candidate.id: medium_candidate},
        versions={"cpv-medium-3": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(shortlisted_for_vacancy=[medium_match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            medium_candidate.user_id: SimpleNamespace(id=medium_candidate.user_id, display_name="Medium Candidate"),
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
    assert result["fit_band"] == "medium"
    assert medium_match.status == MATCH_STATUS_MANAGER_DECISION_PENDING
    assert service.notifications.rows[0].payload_json["message_entries"][0]["text"].startswith(
        "I found a medium-fit candidate"
    )


def test_dispatch_manager_batch_for_vacancy_labels_not_fit_batch_explicitly() -> None:
    vacancy = SimpleNamespace(id="vacancy-fit-4", manager_user_id="manager-fit-4", role_title="Node.js Developer")
    candidate = SimpleNamespace(id="candidate-not-fit", user_id="candidate-user-not-fit")
    not_fit_match = SimpleNamespace(
        id="match-not-fit-4",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-not-fit-4",
        status="shortlisted",
        rationale_json={"fit_band": "not_fit", "gap_signals": ["Core stack overlap is partial."]},
        llm_rank_position=1,
        llm_rank_score=0.41,
        deterministic_score=0.39,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={"cpv-not-fit-4": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(shortlisted_for_vacancy=[not_fit_match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Stretch Candidate"),
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
    assert result["fit_band"] == "not_fit"
    assert not_fit_match.status == MATCH_STATUS_MANAGER_DECISION_PENDING
    assert service.notifications.rows[0].payload_json["message_entries"][0]["text"].startswith(
        "I found a below-threshold candidate"
    )


def test_render_vacancy_card_suppresses_stale_take_home_stage_when_flag_disabled() -> None:
    vacancy = SimpleNamespace(
        id="vacancy-card-1",
        manager_user_id="manager-card-1",
        role_title="Node.js Developer",
        project_description="AI repricing platform for ecommerce sellers.",
        budget_min=6000,
        budget_max=6000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        required_english_level="B2",
        hiring_stages_json=["take_home", "technical_interview"],
        has_take_home_task=False,
        has_live_coding=False,
    )
    candidate = SimpleNamespace(id="candidate-card-1", user_id="candidate-user-card-1")
    match = SimpleNamespace(
        id="match-card-1",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-card-1",
        status="candidate_decision_pending",
        rationale_json={"fit_band": "strong", "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={"cpv-card-1": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Candidate"),
            vacancy.manager_user_id: SimpleNamespace(id=vacancy.manager_user_id, display_name="Manager"),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={vacancy.manager_user_id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    message = service._render_vacancy_card_message(match=match)

    assert "take-home task" not in message.lower()
    assert "technical interview" in message.lower()


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


def test_execute_candidate_pre_interview_action_without_slot_uses_current_card() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-current", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-current", user_id=candidate_user.id)
    vacancy = SimpleNamespace(id="vacancy-current", role_title="Backend Engineer")
    match = SimpleNamespace(
        id="match-current",
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
        raw_message_id="raw-current-candidate",
        action="apply_to_vacancy",
        vacancy_slot=None,
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
    assert "active candidate decisions" in text
    assert "review one of the current profiles first" in text


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
    assert "The hiring manager already approved the connection" in candidate_notification.payload_json["message_entries"][1]["text"]


def test_execute_manager_pre_interview_action_without_slot_uses_current_card() -> None:
    manager_user = SimpleNamespace(id="manager-current", is_hiring_manager=True, is_candidate=False)
    candidate = SimpleNamespace(id="candidate-current-manager", user_id="candidate-user-current-manager")
    vacancy = SimpleNamespace(id="vacancy-current-manager", manager_user_id=manager_user.id, role_title="Node.js Developer")
    match = SimpleNamespace(
        id="match-current-manager",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-current-manager",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={"cpv-current-manager": SimpleNamespace(summary_json={})},
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[match], active_vacancy=[])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Current Candidate"),
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
        raw_message_id="raw-current-manager",
        action="interview_candidate",
        candidate_slot=None,
    )

    assert result is not None
    assert result.status == "awaiting_candidate"
    assert match.status == MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED


def test_dispatch_manager_batch_for_vacancy_blocks_new_card_when_other_vacancy_already_has_active_review() -> None:
    manager_user_id = "manager-multi-queue"
    vacancy_a = SimpleNamespace(id="vacancy-a", manager_user_id=manager_user_id, role_title="Node.js Developer")
    vacancy_b = SimpleNamespace(id="vacancy-b", manager_user_id=manager_user_id, role_title="Python Developer")
    current_candidate = SimpleNamespace(id="candidate-current-a", user_id="candidate-user-current-a")
    queued_candidate = SimpleNamespace(id="candidate-queued-b", user_id="candidate-user-queued-b")
    current_match = SimpleNamespace(
        id="match-current-a",
        vacancy_id=vacancy_a.id,
        candidate_profile_id=current_candidate.id,
        candidate_profile_version_id="cpv-current-a",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "gap_signals": []},
    )
    queued_match = SimpleNamespace(
        id="match-queued-b",
        vacancy_id=vacancy_b.id,
        candidate_profile_id=queued_candidate.id,
        candidate_profile_version_id="cpv-queued-b",
        status="shortlisted",
        rationale_json={"fit_band": "strong", "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={
            current_candidate.id: current_candidate,
            queued_candidate.id: queued_candidate,
        },
        versions={
            "cpv-current-a": SimpleNamespace(summary_json={}),
            "cpv-queued-b": SimpleNamespace(summary_json={}),
        },
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(
        pre_vacancy=[current_match],
        shortlisted_for_vacancy=[queued_match],
    )
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            current_candidate.user_id: SimpleNamespace(id=current_candidate.user_id, display_name="Current Candidate"),
            queued_candidate.user_id: SimpleNamespace(id=queued_candidate.user_id, display_name="Queued Candidate"),
            manager_user_id: SimpleNamespace(id=manager_user_id, display_name="Manager"),
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy_a.id: vacancy_a, vacancy_b.id: vacancy_b},
        manager_vacancies={manager_user_id: [vacancy_a, vacancy_b]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.dispatch_manager_batch_for_vacancy(
        vacancy_id=vacancy_b.id,
        force=False,
        trigger_type="job",
    )

    assert result["status"] == "already_presented"
    assert result["active_vacancy_id"] == vacancy_a.id
    assert queued_match.status == "shortlisted"
    assert service.notifications.rows == []


def test_execute_manager_pre_interview_action_dispatches_next_card_from_other_vacancy_queue() -> None:
    manager_user = SimpleNamespace(id="manager-next-queue", is_hiring_manager=True, is_candidate=False)
    current_candidate = SimpleNamespace(id="candidate-current-next", user_id="candidate-user-current-next")
    queued_candidate = SimpleNamespace(id="candidate-queued-next", user_id="candidate-user-queued-next")
    vacancy_a = SimpleNamespace(id="vacancy-a-next", manager_user_id=manager_user.id, role_title="Node.js Developer")
    vacancy_b = SimpleNamespace(id="vacancy-b-next", manager_user_id=manager_user.id, role_title="Python Developer")
    current_match = SimpleNamespace(
        id="match-current-next",
        vacancy_id=vacancy_a.id,
        candidate_profile_id=current_candidate.id,
        candidate_profile_version_id="cpv-current-next",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "gap_signals": []},
    )
    queued_match = SimpleNamespace(
        id="match-queued-next",
        vacancy_id=vacancy_b.id,
        candidate_profile_id=queued_candidate.id,
        candidate_profile_version_id="cpv-queued-next",
        status="shortlisted",
        rationale_json={"fit_band": "strong", "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={
            current_candidate.id: current_candidate,
            queued_candidate.id: queued_candidate,
        },
        versions={
            "cpv-current-next": SimpleNamespace(summary_json={}),
            "cpv-queued-next": SimpleNamespace(summary_json={}),
        },
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(
        pre_vacancy=[current_match],
        shortlisted_for_vacancy=[queued_match],
        active_vacancy=[],
    )
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            current_candidate.user_id: SimpleNamespace(id=current_candidate.user_id, display_name="Current Candidate"),
            queued_candidate.user_id: SimpleNamespace(id=queued_candidate.user_id, display_name="Queued Candidate"),
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy_a.id: vacancy_a, vacancy_b.id: vacancy_b},
        manager_vacancies={manager_user.id: [vacancy_a, vacancy_b]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    result = service.execute_manager_pre_interview_action(
        user=manager_user,
        raw_message_id="raw-next-queue",
        action="skip_candidate",
        candidate_slot=None,
        match_id=current_match.id,
    )

    assert result is not None
    assert result.status == "skipped"
    assert current_match.status == MATCH_STATUS_MANAGER_SKIPPED
    assert queued_match.status == MATCH_STATUS_MANAGER_DECISION_PENDING
    assert any(
        row.template_key == "manager_pre_interview_review_ready"
        and row.payload_json.get("message_entries")
        and row.payload_json["message_entries"][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "mgr_pre:int:match-queued-next"
        for row in service.notifications.rows
    )


def test_answer_candidate_review_question_uses_current_vacancy_details() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-q", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-q", user_id=candidate_user.id)
    vacancy = SimpleNamespace(
        id="vacancy-q",
        role_title="Senior Node.js Developer",
        project_description="Realtime data pipeline for marketplace analytics.",
        budget_min=6000,
        budget_max=7000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        required_english_level="B2",
        primary_tech_stack_json=["Node.js", "Redis", "GCP"],
        current_version_id="vacancy-version-q",
    )
    match = SimpleNamespace(
        id="match-q",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        vacancy_version_id="vacancy-version-q",
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": ["Node.js and backend overlap"], "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={"vacancy-version-q": SimpleNamespace(approval_summary_text="Marketplace analytics backend role.")},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_candidate_review_question(
        user=candidate_user,
        question_text="А о чем проект?",
    )

    assert answer is not None
    assert "Realtime data pipeline" in answer


def test_block_candidate_more_request_allows_detail_question_about_current_vacancy() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-block", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-block", user_id=candidate_user.id)
    vacancy = SimpleNamespace(
        id="vacancy-block",
        role_title="Senior Node.js Developer",
        current_version_id="vacancy-version-block",
    )
    match = SimpleNamespace(
        id="match-block",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        vacancy_version_id="vacancy-version-block",
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": [], "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={"vacancy-version-block": SimpleNamespace()},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    blocked = service.block_candidate_more_request(
        user=candidate_user,
        text="а есть еще детали по этой вакансии?",
    )

    assert blocked is None


def test_answer_candidate_review_question_returns_team_size_directly() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-team-direct", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-team-direct", user_id=candidate_user.id)
    vacancy = SimpleNamespace(
        id="vacancy-team-direct",
        role_title="Senior Backend Engineer",
        team_size=6,
        current_version_id="vacancy-version-team-direct",
    )
    match = SimpleNamespace(
        id="match-team-direct",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        vacancy_version_id="vacancy-version-team-direct",
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": [], "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={"vacancy-version-team-direct": SimpleNamespace()},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_candidate_review_question(
        user=candidate_user,
        question_text="а сколько человек в команде?",
    )

    assert answer is not None
    assert "6" in answer


def test_answer_candidate_review_question_returns_source_excerpt_for_full_description() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-full-jd", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-full-jd", user_id=candidate_user.id)
    vacancy = SimpleNamespace(
        id="vacancy-full-jd",
        role_title="Senior Node.js Developer",
        current_version_id="vacancy-version-full-jd",
    )
    match = SimpleNamespace(
        id="match-full-jd",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        vacancy_version_id="vacancy-version-full-jd",
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": [], "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={
            "vacancy-version-full-jd": SimpleNamespace(
                extracted_text="5+ years with Node.js, Express, MongoDB, Redis, APIs, and testing in an international team."
            )
        },
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_candidate_review_question(
        user=candidate_user,
        question_text="а полное описание вакансии?",
    )

    assert answer is not None
    assert "Node.js" in answer
    assert "Express" in answer


def test_answer_candidate_review_question_handles_generic_more_details_without_repeating_full_summary() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-more-details", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-more-details", user_id=candidate_user.id)
    vacancy = SimpleNamespace(
        id="vacancy-more-details",
        role_title="Senior Backend Engineer",
        team_size=6,
        project_description="repriced.ai",
        current_version_id="vacancy-version-more-details",
    )
    match = SimpleNamespace(
        id="match-more-details",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        vacancy_version_id="vacancy-version-more-details",
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": [], "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={"vacancy-version-more-details": SimpleNamespace()},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_candidate_review_question(
        user=candidate_user,
        question_text="что то еще?",
    )

    assert answer is not None
    assert "6" in answer
    assert "repriced.ai" in answer


def test_answer_manager_review_question_uses_current_candidate_details() -> None:
    manager_user = SimpleNamespace(id="manager-user-q", is_hiring_manager=True, is_candidate=False)
    candidate = SimpleNamespace(
        id="candidate-manager-q",
        user_id="candidate-user-manager-q",
        salary_min=5000,
        salary_currency="USD",
        salary_period="month",
        location_text="Kyiv, Ukraine",
        work_formats_json=["remote"],
        work_format="remote",
        english_level="b2",
        current_version_id="cpv-manager-q",
    )
    vacancy = SimpleNamespace(id="vacancy-manager-q", manager_user_id=manager_user.id, role_title="Node.js Developer")
    match = SimpleNamespace(
        id="match-manager-q",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-manager-q",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": ["Strong backend overlap"], "gap_signals": []},
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={
            "cpv-manager-q": SimpleNamespace(
                summary_json={
                    "approval_summary_text": "Senior backend engineer with REST API and platform experience.",
                    "skills": ["Python", "Node.js", "Redis"],
                    "years_experience": 6,
                }
            )
        },
    )
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Milana"),
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={manager_user.id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_manager_review_question(
        user=manager_user,
        question_text="Какая у кандидата зарплата?",
    )

    assert answer is not None
    assert "5000 USD per month" in answer


def test_answer_candidate_review_question_uses_dossier_fallback_for_company_question(monkeypatch) -> None:
    candidate_user = SimpleNamespace(id="candidate-user-company", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="candidate-company", user_id=candidate_user.id)
    vacancy = SimpleNamespace(
        id="vacancy-company",
        role_title="Senior Backend Engineer",
        project_description=None,
        budget_min=6000,
        budget_max=7000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        required_english_level="B2",
        primary_tech_stack_json=["Node.js"],
        team_size=9,
        current_version_id="vacancy-version-company",
    )
    match = SimpleNamespace(
        id="match-company",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        vacancy_version_id="vacancy-version-company",
        status=MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": [], "gap_signals": []},
    )

    captured = {}

    def _fake_safe_answer(session, *, question_text, dossier):
        captured["question_text"] = question_text
        captured["dossier"] = dossier
        return SimpleNamespace(payload={"message": "По этой карточке вижу только проект repriced.ai, без отдельного company profile."})

    monkeypatch.setattr("src.matching.review.safe_answer_candidate_review_object_question", _fake_safe_answer)

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate}, active_candidate=candidate)
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_candidate=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = FakeEvaluationsRepository()
    service.users = FakeUsersRepository({candidate_user.id: candidate_user})
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        versions={"vacancy-version-company": SimpleNamespace(approval_summary_text="Backend team role.")},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_candidate_review_question(
        user=candidate_user,
        question_text="Какая компания?",
    )

    assert answer == "По этой карточке вижу только проект repriced.ai, без отдельного company profile."
    assert captured["dossier"]["vacancy"]["team_size"] == 9


def test_answer_manager_review_question_uses_dossier_fallback_for_verification(monkeypatch) -> None:
    manager_user = SimpleNamespace(id="manager-user-verification", is_hiring_manager=True, is_candidate=False)
    candidate = SimpleNamespace(
        id="candidate-manager-verification",
        user_id="candidate-user-verification",
        current_version_id="cpv-manager-verification",
    )
    vacancy = SimpleNamespace(id="vacancy-manager-verification", manager_user_id=manager_user.id, role_title="Node.js Developer")
    match = SimpleNamespace(
        id="match-manager-verification",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id="cpv-manager-verification",
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
        rationale_json={"fit_band": "strong", "matched_signals": [], "gap_signals": []},
    )

    captured = {}

    def _fake_safe_answer(session, *, question_text, dossier):
        captured["question_text"] = question_text
        captured["dossier"] = dossier
        return SimpleNamespace(payload={"message": "Да, по этой карточке вижу, что кандидат прошел verification."})

    monkeypatch.setattr("src.matching.review.safe_answer_manager_review_object_question", _fake_safe_answer)

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(
        candidate_by_id={candidate.id: candidate},
        versions={
            "cpv-manager-verification": SimpleNamespace(
                summary_json={"approval_summary_text": "Senior backend engineer."}
            )
        },
    )
    service.verifications = SimpleNamespace(
        get_latest_submitted_by_profile_id=lambda profile_id: SimpleNamespace(
            status="submitted",
            attempt_no=1,
            submitted_at="2026-03-19 12:00:00+00:00",
        )
    )
    service.matches = FakeMatchingRepository(pre_vacancy=[match])
    service.notifications = FakeNotificationsRepository()
    service.evaluations = SimpleNamespace(get_by_match_id=lambda match_id: None, create_introduction_event=lambda **kwargs: SimpleNamespace(**kwargs))
    service.users = FakeUsersRepository(
        {
            candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Milana"),
            manager_user.id: manager_user,
        }
    )
    service.vacancies = FakeVacanciesRepository(
        vacancies={vacancy.id: vacancy},
        manager_vacancies={manager_user.id: [vacancy]},
    )
    service.messaging = FakeMessagingService()
    service.state_service = FakeStateService(service.matches)

    answer = service.answer_manager_review_question(
        user=manager_user,
        question_text="Кандидат верифицирован?",
    )

    assert answer == "Да, по этой карточке вижу, что кандидат прошел verification."
    assert captured["dossier"]["verification"]["latest_submitted_status"] == "submitted"


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


def test_execute_candidate_pre_interview_skip_prompts_feedback_after_three_skips() -> None:
    candidate_user = SimpleNamespace(id="candidate-user-feedback", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(
        id="candidate-feedback",
        user_id=candidate_user.id,
        questions_context_json={"matching_feedback": {"candidate_skip_streak": 2}},
    )
    vacancy = SimpleNamespace(id="vacancy-feedback", manager_user_id="manager-feedback", role_title="Platform Engineer")
    match = SimpleNamespace(
        id="match-feedback",
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
    service.dispatch_candidate_batch_for_profile = lambda **kwargs: {
        "status": "empty",
        "batch_count": 0,
        "notified": False,
    }

    result = service.execute_candidate_pre_interview_action(
        user=candidate_user,
        raw_message_id="raw-feedback-candidate",
        action="skip_vacancy",
        vacancy_slot=1,
    )

    assert result is not None
    assert result.status == "skipped"
    assert candidate.questions_context_json["matching_feedback"]["candidate_skip_streak"] == 3
    assert any(
        "I’ve seen a few skips in a row" in row.payload_json["text"]
        and "update your matching preferences right here" in row.payload_json["text"]
        for row in service.notifications.rows
    )


def test_execute_manager_pre_interview_skip_prompts_feedback_after_three_skips() -> None:
    manager_user = SimpleNamespace(id="manager-user-feedback", is_candidate=False, is_hiring_manager=True)
    candidate = SimpleNamespace(id="candidate-manager-feedback", user_id="candidate-manager-user-feedback")
    vacancy = SimpleNamespace(
        id="vacancy-manager-feedback",
        manager_user_id=manager_user.id,
        role_title="Staff Engineer",
        questions_context_json={"matching_feedback": {"manager_skip_streak": 2}},
    )
    match = SimpleNamespace(
        id="match-manager-feedback",
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        status=MATCH_STATUS_MANAGER_DECISION_PENDING,
    )

    service = MatchingReviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate_by_id={candidate.id: candidate})
    service.verifications = FakeVerificationRepository()
    service.matches = FakeMatchingRepository(pre_vacancy=[match], active_vacancy=[])
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
        raw_message_id="raw-feedback-manager",
        action="skip_candidate",
        candidate_slot=1,
    )

    assert result is not None
    assert result.status == "skipped"
    assert vacancy.questions_context_json["matching_feedback"]["manager_skip_streak"] == 3
    assert any(
        "I’ve seen a few skips in a row on this vacancy" in row.payload_json["text"]
        and "update the vacancy right here" in row.payload_json["text"]
        for row in service.notifications.rows
    )


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
    assert "active candidate decisions on this vacancy" in text
    assert "move one of the current profiles forward" in text


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
