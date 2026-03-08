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

    def get_by_manager_user_id(self, user_id):
        return [self.vacancy] if self.vacancy is not None else []


class FakeMatchingRepository:
    def __init__(self, manager_review_match=None):
        self.manager_review_match = manager_review_match

    def get_latest_manager_review_for_manager(self, vacancy_ids, *, manager_review_only: bool = True):
        return self.manager_review_match


def test_graph_manager_stage_handles_intake_pending_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v1", state="INTAKE_PENDING")
    )
    service.matches = FakeMatchingRepository()

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


def test_graph_manager_stage_does_not_treat_intake_question_as_jd_submission() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v1q", state="INTAKE_PENDING")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m1q",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Can I just paste the job details here?",
    )

    assert result is not None
    assert result.stage == "INTAKE_PENDING"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_manager_stage_allows_passthrough_for_real_jd_text() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v2", state="INTAKE_PENDING")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Senior Python engineer, fintech product, remote in Europe, budget 6000 EUR.",
    )

    assert result is not None
    assert result.stage == "INTAKE_PENDING"
    assert result.action_accepted is True
    assert result.proposed_action == "send_job_description_text"
    assert "Senior Python engineer" in result.structured_payload["job_description_text"]


def test_graph_manager_stage_handles_clarification_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v3", state="CLARIFICATION_QA")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m3",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What exactly do you still need from me?",
    )

    assert reply is not None
    assert "budget" in reply.lower() or "vacancy" in reply.lower()


def test_graph_manager_stage_handles_vacancy_summary_review_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v3a", state="VACANCY_SUMMARY_REVIEW")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m3a",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Why do I need to approve this summary?",
    )

    assert reply is not None
    assert "approve" in reply.lower() or "summary" in reply.lower()


def test_graph_manager_stage_does_not_treat_approval_question_as_summary_edit() -> None:
    service = LangGraphStageAgentService(session=object())
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v3aa", state="VACANCY_SUMMARY_REVIEW")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m3aa",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="How long will this take before I can continue?",
    )

    assert result is not None
    assert result.stage == "VACANCY_SUMMARY_REVIEW"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


def test_graph_manager_stage_accepts_vacancy_summary_approve() -> None:
    service = LangGraphStageAgentService(session=object())
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v3b", state="VACANCY_SUMMARY_REVIEW")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m3b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Approve summary",
    )

    assert result is not None
    assert result.stage == "VACANCY_SUMMARY_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "approve_summary"


def test_graph_manager_stage_accepts_real_clarification_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v4", state="CLARIFICATION_QA")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message=(
            "Budget: 7000-9000 USD per month. Countries: Poland and Germany. Remote. "
            "Team size: 6. Project: B2B payments platform. Primary stack: Python, FastAPI, PostgreSQL."
        ),
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is True
    assert result.proposed_action == "send_vacancy_clarifications"
    assert result.structured_payload["budget_min"] == 7000
    assert result.structured_payload["work_format"] == "remote"


def test_graph_manager_stage_handles_open_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v5", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m5",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What happens now and when will I see candidates?",
    )

    assert reply is not None
    assert "candidate" in reply.lower() or "match" in reply.lower()


def test_graph_manager_stage_accepts_open_delete_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m6",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Delete vacancy",
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is True
    assert result.proposed_action == "delete_vacancy"
    assert result.stage_status == "ready_for_transition"


def test_graph_manager_stage_handles_manager_review_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v7", state="OPEN")
    )
    service.matches = FakeMatchingRepository(
        manager_review_match=SimpleNamespace(id="m1", status="manager_review")
    )

    user = SimpleNamespace(
        id="m7",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="What happens if I approve this candidate?",
    )

    assert reply is not None
    assert "approve" in reply.lower() or "candidate" in reply.lower()


def test_graph_manager_stage_accepts_manager_review_approve() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v8", state="OPEN")
    )
    service.matches = FakeMatchingRepository(
        manager_review_match=SimpleNamespace(id="m2", status="manager_review")
    )

    user = SimpleNamespace(
        id="m8",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Approve candidate",
    )

    assert result is not None
    assert result.stage == "MANAGER_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "approve_candidate"
    assert result.stage_status == "ready_for_transition"


def test_graph_manager_stage_handles_delete_confirmation_help() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v9",
            state="OPEN",
            questions_context_json={"deletion": {"pending": True}},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m9",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Can I cancel this instead of deleting the vacancy?",
    )

    assert reply is not None
    assert "cancel" in reply.lower() or "vacancy" in reply.lower()


def test_graph_manager_stage_accepts_delete_confirmation() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v10",
            state="OPEN",
            questions_context_json={"deletion": {"pending": True}},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m10",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Confirm delete vacancy",
    )

    assert result is not None
    assert result.stage == "DELETE_CONFIRMATION"
    assert result.action_accepted is True
    assert result.proposed_action == "confirm_delete"
    assert result.stage_status == "ready_for_transition"


def test_graph_manager_stage_does_not_treat_delete_question_as_confirm() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v10a",
            state="OPEN",
            questions_context_json={"deletion": {"pending": True}},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m10a",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="What exactly will be cancelled if I confirm?",
    )

    assert result is not None
    assert result.stage == "DELETE_CONFIRMATION"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None
