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


def test_graph_candidate_stage_allows_passthrough_for_real_cv_text() -> None:
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

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Senior backend engineer with 7 years in Python, Go, AWS, and PostgreSQL.",
    )

    assert reply is None


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


def test_graph_candidate_stage_allows_passthrough_for_real_summary_correction() -> None:
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

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="The summary is wrong: I work mostly with Go, not Python.",
    )

    assert reply is None


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


def test_graph_candidate_stage_allows_passthrough_for_real_questions_answer() -> None:
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

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="3000 USD net per month, Warsaw, remote.",
    )

    assert reply is None


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
