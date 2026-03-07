from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


def test_graph_entry_service_handles_contact_required() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=False)

    user = SimpleNamespace(
        id="u1",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_entry_reply(
        user=user,
        latest_user_message="Why do you need my contact?",
    )

    assert reply is not None
    assert "contact" in reply.lower()


def test_graph_entry_service_handles_consent_required() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=False)

    user = SimpleNamespace(
        id="u2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_entry_reply(
        user=user,
        latest_user_message="Why do you need consent?",
    )

    assert reply is not None
    assert "consent" in reply.lower() or "data" in reply.lower()


def test_graph_entry_service_handles_role_selection() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)

    user = SimpleNamespace(
        id="u3",
        phone_number="+123",
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
