from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


class StatefulCandidateProfilesRepository:
    def __init__(self, candidate):
        self.candidate = candidate

    def get_active_by_user_id(self, user_id):
        return self.candidate


class StatefulVacanciesRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_latest_active_by_manager_user_id(self, manager_user_id):
        return self.vacancy

    def get_by_manager_user_id(self, user_id):
        return [self.vacancy] if self.vacancy is not None else []


class StatefulInterviewsRepository:
    def __init__(self):
        self.active_session = None

    def get_active_session_for_candidate(self, candidate_profile_id):
        return self.active_session


class StatefulMatchesRepository:
    def __init__(self):
        self.invited_match = None
        self.manager_review_match = None

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        return self.invited_match

    def get_latest_manager_review_for_manager(self, vacancy_ids, *, manager_review_only: bool = True):
        return self.manager_review_match


def _build_candidate_interaction_service(candidate):
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = StatefulCandidateProfilesRepository(candidate)
    service.interviews = StatefulInterviewsRepository()
    service.matches = StatefulMatchesRepository()
    return service


def _build_manager_interaction_service(vacancy):
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = StatefulVacanciesRepository(vacancy)
    service.matches = StatefulMatchesRepository()
    return service


def test_candidate_interaction_graph_flow_progresses_from_invite_to_interview_and_delete() -> None:
    candidate = SimpleNamespace(id="cp-int", state="READY", questions_context_json={})
    service = _build_candidate_interaction_service(candidate)
    service.matches.invited_match = SimpleNamespace(id="match1", status="invited")

    user = SimpleNamespace(
        id="u-int",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    invite_help = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="How long is the interview and can I answer by voice?",
    )
    assert invite_help is not None
    assert "interview" in invite_help.lower() or "voice" in invite_help.lower()

    accept_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Accept interview",
    )
    assert accept_result is not None
    assert accept_result.stage == "INTERVIEW_INVITED"
    assert accept_result.action_accepted is True
    assert accept_result.proposed_action == "accept_interview"

    service.interviews.active_session = SimpleNamespace(id="session1", state="IN_PROGRESS")
    answer_result = service.maybe_run_stage(
        user=user,
        latest_user_message="I designed the API boundary and implemented the event-driven processing pipeline.",
    )
    assert answer_result is not None
    assert answer_result.stage == "INTERVIEW_IN_PROGRESS"
    assert answer_result.action_accepted is True
    assert answer_result.proposed_action == "answer_current_question"
    assert "implemented" in answer_result.structured_payload["answer_text"].lower()

    candidate.questions_context_json = {"deletion": {"pending": True}}
    delete_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Confirm delete profile",
    )
    assert delete_result is not None
    assert delete_result.stage == "DELETE_CONFIRMATION"
    assert delete_result.action_accepted is True
    assert delete_result.proposed_action == "confirm_delete"


def test_manager_interaction_graph_flow_progresses_from_review_to_delete() -> None:
    vacancy = SimpleNamespace(id="v-int", state="OPEN", questions_context_json={})
    service = _build_manager_interaction_service(vacancy)
    service.matches.manager_review_match = SimpleNamespace(id="review1", status="manager_review")

    user = SimpleNamespace(
        id="m-int",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    review_help = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What happens if I approve this candidate?",
    )
    assert review_help is not None
    assert "approve" in review_help.lower() or "candidate" in review_help.lower()

    approve_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Approve candidate",
    )
    assert approve_result is not None
    assert approve_result.stage == "MANAGER_REVIEW"
    assert approve_result.action_accepted is True
    assert approve_result.proposed_action == "approve_candidate"

    vacancy.questions_context_json = {"deletion": {"pending": True}}
    service.matches.manager_review_match = None
    delete_help = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What exactly gets cancelled if I confirm?",
    )
    assert delete_help is not None
    assert "delete" in delete_help.lower() or "cancel" in delete_help.lower()

    delete_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Cancel delete",
    )
    assert delete_result is not None
    assert delete_result.stage == "DELETE_CONFIRMATION"
    assert delete_result.action_accepted is True
    assert delete_result.proposed_action == "cancel_delete"
