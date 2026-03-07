from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


class FakeVacanciesRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_latest_active_by_manager_user_id(self, manager_user_id):
        return self.vacancy


def test_graph_manager_stage_handles_intake_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v1", state="INTAKE_PENDING")
    )

    user = SimpleNamespace(
        id="m1",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Can I just paste the job details here?",
    )

    assert reply is not None
    assert "text" in reply.lower() or "job" in reply.lower()


def test_graph_manager_stage_allows_passthrough_for_real_jd_text() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v2", state="INTAKE_PENDING")
    )

    user = SimpleNamespace(
        id="m2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Senior Python engineer, fintech product, remote in Europe, budget 6000 EUR.",
    )

    assert reply is None
