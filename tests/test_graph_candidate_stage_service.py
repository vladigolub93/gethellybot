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


def test_graph_candidate_stage_handles_cv_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp1", state="CV_PENDING")
    )

    user = SimpleNamespace(
        id="u4",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="If I don't have a CV yet?",
    )

    assert reply is not None
    assert "cv" in reply.lower() or "experience" in reply.lower()


def test_graph_candidate_stage_accepts_real_cv_text_transition() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp2", state="CV_PENDING")
    )

    user = SimpleNamespace(
        id="u5",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Senior backend engineer with 7 years in Python, Go, AWS, and PostgreSQL.",
    )

    assert result is not None
    assert result.stage == "CV_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_cv_text"
    assert result.stage_status == "ready_for_transition"
    assert "Senior backend engineer" in result.structured_payload["cv_text"]


def test_graph_candidate_stage_handles_summary_review_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp3", state="SUMMARY_REVIEW")
    )

    user = SimpleNamespace(
        id="u6",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What should I change if something is wrong in this summary?",
    )

    assert reply is not None
    assert "summary" in reply.lower() or "approve" in reply.lower()


def test_graph_candidate_stage_accepts_summary_review_correction() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp4", state="SUMMARY_REVIEW")
    )

    user = SimpleNamespace(
        id="u7",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="The summary is wrong: I work mostly with Go, not Python.",
    )

    assert result is not None
    assert result.stage == "SUMMARY_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "request_summary_change"
    assert "Go" in result.structured_payload["edit_text"]


def test_graph_candidate_stage_accepts_summary_approve() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp4a", state="SUMMARY_REVIEW")
    )

    user = SimpleNamespace(
        id="u7a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Approve summary",
    )

    assert result is not None
    assert result.stage == "SUMMARY_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "approve_summary"


def test_graph_candidate_stage_handles_questions_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp5", state="QUESTIONS_PENDING")
    )

    user = SimpleNamespace(
        id="u8",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Why do you need my salary and location?",
    )

    assert reply is not None
    assert "salary" in reply.lower() or "matching" in reply.lower()


def test_graph_candidate_stage_accepts_real_questions_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp6", state="QUESTIONS_PENDING")
    )

    user = SimpleNamespace(
        id="u9",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="3000 USD net per month. Location: Warsaw. Remote.",
    )

    assert result is not None
    assert result.stage == "QUESTIONS_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_salary_location_work_format"
    assert result.structured_payload["salary_min"] == 3000
    assert result.structured_payload["location_text"] == "Warsaw"
    assert result.structured_payload["work_format"] == "remote"


def test_graph_candidate_stage_handles_verification_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp7", state="VERIFICATION_PENDING")
    )

    user = SimpleNamespace(
        id="u10",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="I cannot record video now because I am on desktop.",
    )

    assert reply is not None
    assert "video" in reply.lower() or "later" in reply.lower()


def test_graph_candidate_stage_accepts_verification_video_submission() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp7a", state="VERIFICATION_PENDING")
    )

    user = SimpleNamespace(
        id="u10a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="",
        latest_message_type="video",
    )

    assert result is not None
    assert result.stage == "VERIFICATION_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_verification_video"
    assert result.stage_status == "ready_for_transition"
    assert result.structured_payload["submission_type"] == "video"


def test_graph_candidate_stage_handles_ready_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp8", state="READY")
    )

    user = SimpleNamespace(
        id="u11",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What should I do next?",
    )

    assert reply is not None
    assert "ready" in reply.lower() or "match" in reply.lower()
