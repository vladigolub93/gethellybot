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


def _build_candidate_service(candidate):
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = StatefulCandidateProfilesRepository(candidate)
    service.interviews = StatefulInterviewsRepository()
    service.matches = StatefulMatchesRepository()
    return service


def _build_manager_service(vacancy):
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = StatefulVacanciesRepository(vacancy)
    service.matches = StatefulMatchesRepository()
    return service


def test_candidate_graph_flow_progresses_across_stage_sequence() -> None:
    candidate = SimpleNamespace(id="cp-flow", state="CV_PENDING", questions_context_json={})
    service = _build_candidate_service(candidate)
    user = SimpleNamespace(
        id="u-flow",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    cv_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Senior backend engineer with 7 years in Python, Go, AWS, and PostgreSQL.",
    )
    assert cv_result is not None
    assert cv_result.stage == "CV_PENDING"
    assert cv_result.action_accepted is True
    assert cv_result.proposed_action == "send_cv_text"

    candidate.state = "SUMMARY_REVIEW"
    summary_result = service.maybe_run_stage(
        user=user,
        latest_user_message="The summary is wrong: I work mostly with Go, not Python.",
    )
    assert summary_result is not None
    assert summary_result.stage == "SUMMARY_REVIEW"
    assert summary_result.action_accepted is True
    assert summary_result.proposed_action == "request_summary_change"

    approve_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Approve summary",
    )
    assert approve_result is not None
    assert approve_result.stage == "SUMMARY_REVIEW"
    assert approve_result.action_accepted is True
    assert approve_result.proposed_action == "approve_summary"

    candidate.state = "QUESTIONS_PENDING"
    questions_result = service.maybe_run_stage(
        user=user,
        latest_user_message="3000 USD net per month, Warsaw, remote.",
    )
    assert questions_result is not None
    assert questions_result.stage == "QUESTIONS_PENDING"
    assert questions_result.action_accepted is True
    assert questions_result.proposed_action == "send_salary_location_work_format"
    assert questions_result.structured_payload["salary_min"] == 3000
    assert "work_format" not in questions_result.structured_payload

    candidate.state = "VERIFICATION_PENDING"
    verification_help = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="I cannot record video right now because I am on desktop.",
    )
    assert verification_help is not None
    assert "video" in verification_help.lower() or "desktop" in verification_help.lower()

    verification_result = service.maybe_run_stage(
        user=user,
        latest_user_message="",
        latest_message_type="video",
    )
    assert verification_result is not None
    assert verification_result.stage == "VERIFICATION_PENDING"
    assert verification_result.action_accepted is True
    assert verification_result.proposed_action == "send_verification_video"

    candidate.state = "READY"
    ready_reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What happens now?",
    )
    assert ready_reply is not None
    assert "match" in ready_reply.lower() or "opportunit" in ready_reply.lower()


def test_manager_graph_flow_progresses_across_stage_sequence() -> None:
    vacancy = SimpleNamespace(id="v-flow", state="INTAKE_PENDING", questions_context_json={})
    service = _build_manager_service(vacancy)
    user = SimpleNamespace(
        id="m-flow",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    intake_result = service.maybe_run_stage(
        user=user,
        latest_user_message=(
            "Senior Python engineer for a fintech product. Remote in Europe. "
            "Budget up to 7000 EUR. Team of 6. FastAPI and PostgreSQL."
        ),
    )
    assert intake_result is not None
    assert intake_result.stage == "INTAKE_PENDING"
    assert intake_result.action_accepted is True
    assert intake_result.proposed_action == "send_job_description_text"

    vacancy.state = "CLARIFICATION_QA"
    clarification_result = service.maybe_run_stage(
        user=user,
        latest_user_message=(
            "Budget: 7000-9000 USD per month. Countries: Poland and Germany. Remote. "
            "Team size: 6. Project: B2B payments platform. Primary stack: Python, FastAPI, PostgreSQL."
        ),
    )
    assert clarification_result is not None
    assert clarification_result.stage == "CLARIFICATION_QA"
    assert clarification_result.action_accepted is True
    assert clarification_result.proposed_action == "send_vacancy_clarifications"
    assert clarification_result.structured_payload["budget_min"] == 7000

    vacancy.state = "OPEN"
    open_reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What happens now and when will I see candidates?",
    )
    assert open_reply is not None
    assert "candidate" in open_reply.lower() or "match" in open_reply.lower()

    delete_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Delete vacancy",
    )
    assert delete_result is not None
    assert delete_result.stage == "OPEN"
    assert delete_result.action_accepted is True
    assert delete_result.proposed_action == "delete_vacancy"

    vacancy.questions_context_json = {"deletion": {"pending": True}}
    confirm_result = service.maybe_run_stage(
        user=user,
        latest_user_message="Confirm delete vacancy",
    )
    assert confirm_result is not None
    assert confirm_result.stage == "DELETE_CONFIRMATION"
    assert confirm_result.action_accepted is True
    assert confirm_result.proposed_action == "confirm_delete"
