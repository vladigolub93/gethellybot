from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeRawMessagesRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_recent_text_context(self, *, user_id, limit=6):
        return list(self.rows)[:limit]


def test_graph_entry_service_handles_contact_required() -> None:
    service = LangGraphStageAgentService(session=object())

    user = SimpleNamespace(
        id="u1",
        phone_number=None,
        username=None,
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_entry_reply(
        user=user,
        latest_user_message="Why do you need my contact?",
    )

    assert reply is not None
    assert "contact" in reply.lower() or "username" in reply.lower()


def test_graph_entry_service_does_not_treat_contact_question_as_completion() -> None:
    service = LangGraphStageAgentService(session=object())

    user = SimpleNamespace(
        id="u1q",
        phone_number=None,
        username=None,
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_entry_stage(
        user=user,
        latest_user_message="Can I skip for now?",
    )

    assert result is not None
    assert result.stage == "CONTACT_REQUIRED"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_entry_service_handles_role_selection_when_username_exists() -> None:
    service = LangGraphStageAgentService(session=object())

    user = SimpleNamespace(
        id="u2",
        phone_number=None,
        username="hellyuser",
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_entry_reply(
        user=user,
        latest_user_message="What is the difference?",
    )

    assert reply is not None
    assert "candidate" in reply.lower() or "hiring manager" in reply.lower()


def test_graph_entry_service_does_not_treat_role_question_as_selection() -> None:
    service = LangGraphStageAgentService(session=object())

    user = SimpleNamespace(
        id="u2q",
        phone_number=None,
        username="hellyuser",
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_entry_stage(
        user=user,
        latest_user_message="Which one should I choose?",
    )

    assert result is not None
    assert result.stage == "ROLE_SELECTION"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_entry_service_accepts_role_selection_transition() -> None:
    service = LangGraphStageAgentService(session=object())

    user = SimpleNamespace(
        id="u3",
        phone_number="+123",
        username=None,
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_entry_stage(
        user=user,
        latest_user_message="Candidate",
    )

    assert result is not None
    assert result.stage == "ROLE_SELECTION"
    assert result.action_accepted is True
    assert result.proposed_action == "candidate"
    assert result.stage_status == "ready_for_transition"


def test_graph_entry_service_skips_contact_stage_when_username_exists() -> None:
    service = LangGraphStageAgentService(session=object())

    user = SimpleNamespace(
        id="u4",
        phone_number=None,
        username="hellyuser",
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    result = service.maybe_run_entry_stage(
        user=user,
        latest_user_message="Why should I choose a role first?",
    )

    assert result is not None
    assert result.stage == "ROLE_SELECTION"
    assert result.action_accepted is False


def test_graph_entry_service_passes_recent_turn_memory_to_stage_agent(monkeypatch) -> None:
    service = LangGraphStageAgentService(session=object())
    service.raw_messages = FakeRawMessagesRepository(
        [
            "User: Why do you need this?",
            "Helly: I use your Telegram identity to keep one profile linked to one person.",
        ]
    )

    user = SimpleNamespace(
        id="u5",
        phone_number=None,
        username=None,
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )
    captured = {}

    def _fake_decision(_session, *, latest_user_message, current_step_guidance, recent_context):
        captured["latest_user_message"] = latest_user_message
        captured["current_step_guidance"] = current_step_guidance
        captured["recent_context"] = list(recent_context)
        return SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "I need a usable contact channel to continue.",
                "reason_code": "help_question",
                "needs_follow_up": True,
            }
        )

    monkeypatch.setattr("src.graph.stages.entry.safe_contact_required_decision", _fake_decision)

    result = service.maybe_run_entry_stage(
        user=user,
        latest_user_message="Can I skip for now?",
    )

    assert result is not None
    assert captured["latest_user_message"] == "Can I skip for now?"
    assert "User: Why do you need this?" in captured["recent_context"]
    assert "Helly: I use your Telegram identity to keep one profile linked to one person." in captured["recent_context"]
