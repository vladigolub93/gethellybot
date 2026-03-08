from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeLogger:
    def __init__(self):
        self.calls = []

    def info(self, event, **kwargs):
        self.calls.append({"event": event, **kwargs})


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
    def get_active_session_for_candidate(self, candidate_profile_id):
        return None


class FakeMatchesRepository:
    def get_latest_invited_for_candidate(self, candidate_profile_id):
        return None


def test_graph_entry_stage_emits_execution_log(monkeypatch) -> None:
    fake_logger = FakeLogger()
    monkeypatch.setattr("src.graph.service.logger", fake_logger)

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=False)

    user = SimpleNamespace(
        id="u-log-1",
        telegram_user_id=12345,
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_entry_stage(
        user=user,
        latest_user_message="I agree",
    )

    assert result is not None
    assert fake_logger.calls
    last = fake_logger.calls[-1]
    assert last["event"] == "graph_stage_executed"
    assert last["stage"] == "CONSENT_REQUIRED"
    assert last["stage_status"] == "ready_for_transition"
    assert last["proposed_action"] == "reply_i_agree"
    assert last["action_accepted"] is True
    assert last["telegram_user_id"] == 12345
    assert last["latest_message_type"] == "text"


def test_graph_candidate_stage_emits_execution_log(monkeypatch) -> None:
    fake_logger = FakeLogger()
    monkeypatch.setattr("src.graph.service.logger", fake_logger)

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateProfilesRepository(
        SimpleNamespace(id="cp-log-1", state="CV_PENDING")
    )
    service.interviews = FakeInterviewsRepository()
    service.matches = FakeMatchesRepository()

    user = SimpleNamespace(
        id="u-log-2",
        telegram_user_id=67890,
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
        telegram_chat_id=201,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Senior backend engineer with Python and Go experience.",
    )

    assert result is not None
    assert fake_logger.calls
    last = fake_logger.calls[-1]
    assert last["event"] == "graph_stage_executed"
    assert last["stage"] == "CV_PENDING"
    assert last["stage_status"] == "ready_for_transition"
    assert last["proposed_action"] == "send_cv_text"
    assert last["action_accepted"] is True
    assert last["telegram_user_id"] == 67890
    assert last["latest_message_type"] == "text"
