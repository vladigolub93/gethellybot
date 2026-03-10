from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


class FakeCandidateProfilesRepository:
    def __init__(self, candidate):
        self.candidate = candidate

    def get_active_by_user_id(self, user_id):
        return self.candidate


class FakeInterviewsRepository:
    def __init__(self, active_session=None):
        self.active_session = active_session

    def get_active_session_for_candidate(self, candidate_profile_id):
        return self.active_session


class FakeVacanciesRepository:
    def __init__(self, vacancy=None):
        self.vacancy = vacancy

    def get_latest_active_by_manager_user_id(self, manager_user_id):
        return self.vacancy

    def get_by_manager_user_id(self, user_id):
        return [self.vacancy] if self.vacancy is not None else []


class FakeMatchesRepository:
    def __init__(self, invited_match=None, manager_review_match=None, candidate_review_match=None):
        self.invited_match = invited_match
        self.manager_review_match = manager_review_match
        self.candidate_review_match = candidate_review_match

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        return self.invited_match

    def get_latest_manager_review_for_manager(self, vacancy_ids, *, manager_review_only: bool = True):
        return self.manager_review_match

    def get_latest_pre_interview_review_for_candidate(self, candidate_profile_id):
        return self.candidate_review_match


def _build_candidate_graph_service(*, candidate, active_session=None, invited_match=None, candidate_review_match=None):
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(candidate)
    service.interviews = FakeInterviewsRepository(active_session=active_session)
    service.matches = FakeMatchesRepository(
        invited_match=invited_match,
        candidate_review_match=candidate_review_match,
    )
    return service


def _build_manager_graph_service(*, vacancy, manager_review_match=None):
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(vacancy=vacancy)
    service.matches = FakeMatchesRepository(manager_review_match=manager_review_match)
    return service


def test_candidate_stage_resolution_prefers_ready_when_no_higher_priority_flow_exists() -> None:
    service = _build_candidate_graph_service(
        candidate=SimpleNamespace(id="cp1", state="READY", questions_context_json={}),
    )
    user = SimpleNamespace(
        id="u1",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="What happens now?")

    assert result is not None
    assert result.stage == "READY"


def test_candidate_stage_resolution_prefers_invited_over_ready() -> None:
    service = _build_candidate_graph_service(
        candidate=SimpleNamespace(id="cp2", state="READY", questions_context_json={}),
        invited_match=SimpleNamespace(id="m1", status="invited"),
    )
    user = SimpleNamespace(
        id="u2",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="What is this interview?")

    assert result is not None
    assert result.stage == "INTERVIEW_INVITED"


def test_candidate_stage_resolution_prefers_vacancy_review_over_ready() -> None:
    service = _build_candidate_graph_service(
        candidate=SimpleNamespace(id="cp2b", state="READY", questions_context_json={}),
        candidate_review_match=SimpleNamespace(id="m1b", status="candidate_decision_pending"),
    )
    user = SimpleNamespace(
        id="u2b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="What happens after I apply?")

    assert result is not None
    assert result.stage == "VACANCY_REVIEW"


def test_candidate_stage_resolution_prefers_active_interview_over_invited() -> None:
    service = _build_candidate_graph_service(
        candidate=SimpleNamespace(id="cp3", state="READY", questions_context_json={}),
        active_session=SimpleNamespace(id="i1", state="IN_PROGRESS"),
        invited_match=SimpleNamespace(id="m2", status="invited"),
    )
    user = SimpleNamespace(
        id="u3",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="Here is my answer to the current question.")

    assert result is not None
    assert result.stage == "INTERVIEW_IN_PROGRESS"


def test_candidate_stage_resolution_prefers_pending_delete_over_active_interview() -> None:
    service = _build_candidate_graph_service(
        candidate=SimpleNamespace(
            id="cp4",
            state="READY",
            questions_context_json={"deletion": {"pending": True}},
        ),
        active_session=SimpleNamespace(id="i2", state="IN_PROGRESS"),
        invited_match=SimpleNamespace(id="m3", status="invited"),
    )
    user = SimpleNamespace(
        id="u4",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="Cancel delete")

    assert result is not None
    assert result.stage == "DELETE_CONFIRMATION"


def test_manager_stage_resolution_prefers_open_when_no_higher_priority_flow_exists() -> None:
    service = _build_manager_graph_service(
        vacancy=SimpleNamespace(id="v1", state="OPEN", questions_context_json={}),
    )
    user = SimpleNamespace(
        id="m1",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="What happens now?")

    assert result is not None
    assert result.stage == "OPEN"


def test_manager_stage_resolution_prefers_manager_review_over_open() -> None:
    service = _build_manager_graph_service(
        vacancy=SimpleNamespace(id="v2", state="OPEN", questions_context_json={}),
        manager_review_match=SimpleNamespace(id="m4", status="manager_review"),
    )
    user = SimpleNamespace(
        id="m2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="What happens if I approve this candidate?")

    assert result is not None
    assert result.stage == "MANAGER_REVIEW"


def test_manager_stage_resolution_prefers_pending_delete_over_manager_review() -> None:
    service = _build_manager_graph_service(
        vacancy=SimpleNamespace(
            id="v3",
            state="OPEN",
            questions_context_json={"deletion": {"pending": True}},
        ),
        manager_review_match=SimpleNamespace(id="m5", status="manager_review"),
    )
    user = SimpleNamespace(
        id="m3",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(user=user, latest_user_message="Confirm delete vacancy")

    assert result is not None
    assert result.stage == "DELETE_CONFIRMATION"
