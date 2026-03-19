from types import SimpleNamespace

from src.graph.service import LangGraphStageAgentService


class FakeConsentsRepository:
    def __init__(self, *, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type):
        assert consent_type == "data_processing"
        return self.granted


class FakeVacanciesRepository:
    def __init__(self, vacancy, *, current_version=None):
        if isinstance(vacancy, list):
            self.vacancies = vacancy
        elif vacancy is None:
            self.vacancies = []
        else:
            self.vacancies = [vacancy]
        self.current_version = current_version

    def get_latest_active_by_manager_user_id(self, manager_user_id):
        for vacancy in reversed(self.vacancies):
            if getattr(vacancy, "manager_user_id", manager_user_id) == manager_user_id:
                return vacancy
        return None

    def get_by_manager_user_id(self, user_id):
        return [
            vacancy
            for vacancy in self.vacancies
            if getattr(vacancy, "manager_user_id", user_id) == user_id
        ]

    def get_latest_incomplete_by_manager_user_id(self, manager_user_id):
        return self.get_latest_active_by_manager_user_id(manager_user_id)

    def get_open_by_manager_user_id(self, manager_user_id):
        return self.get_by_manager_user_id(manager_user_id)

    def get_current_version(self, vacancy):
        if self.current_version is None or vacancy is None:
            return None
        return self.current_version


class FakeMatchingRepository:
    def __init__(self, manager_review_match=None, pre_interview_review_match=None):
        self.manager_review_match = manager_review_match
        self.pre_interview_review_match = pre_interview_review_match

    def get_latest_manager_review_for_manager(self, vacancy_ids, *, manager_review_only: bool = True):
        return self.manager_review_match

    def get_latest_pre_interview_review_for_manager(self, vacancy_ids):
        return self.pre_interview_review_match


class FakeCandidateProfilesRepository:
    def __init__(self, candidates):
        self.candidates = list(candidates)

    def get_ready_profiles(self):
        return list(self.candidates)


class FakeEvaluationsRepository:
    def __init__(self, evaluation=None):
        self.evaluation = evaluation

    def get_by_match_id(self, match_id):
        if self.evaluation is None:
            return None
        return self.evaluation if getattr(self.evaluation, "match_id", None) == match_id else None


def test_graph_manager_stage_help_receives_saved_vacancy_memory(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_open_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Let me pull up the vacancy.",
                "reason_code": "help",
            }
        ),
    )

    def _fake_assistance(_session, *, context, latest_user_message, recent_context=None):
        captured["context"] = context
        captured["latest_user_message"] = latest_user_message
        captured["recent_context"] = list(recent_context or [])
        return SimpleNamespace(payload={"response_text": "Here is the saved vacancy summary.", "suggested_action": None})

    monkeypatch.setattr(
        "src.graph.stages.manager.safe_state_assistance_decision",
        _fake_assistance,
    )

    vacancy = SimpleNamespace(
        id="vac-memory",
        state="OPEN",
        manager_user_id="m-memory",
        current_version_id="vv-memory",
        role_title="Senior Python Engineer",
        seniority_normalized="senior",
        budget_min=6000,
        budget_max=7000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        countries_allowed_json=["PL", "UA"],
        primary_tech_stack_json=["python", "postgresql"],
        project_description="Build backend APIs and platform services for a hiring product.",
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        vacancy,
        current_version=SimpleNamespace(
            id="vv-memory",
            approval_summary_text="This vacancy is for a senior Python engineer building backend platform services.",
            summary_json={
                "approval_summary_text": "This vacancy is for a senior Python engineer building backend platform services."
            },
        ),
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m-memory",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Can you show me the vacancy summary again?",
    )

    assert reply == "Here is the saved vacancy summary."
    combined_context = " ".join(captured["recent_context"])
    assert "senior Python engineer building backend platform services" in combined_context
    assert "budget 6000-7000 USD per month" in combined_context
    assert "work format remote" in combined_context
    assert "stack python, postgresql" in combined_context


def test_graph_manager_open_help_explains_matching_blockers(monkeypatch) -> None:
    monkeypatch.setattr("src.llm.service.should_use_llm_runtime", lambda _session: False)

    vacancy = SimpleNamespace(
        id="vac-blockers",
        state="OPEN",
        manager_user_id="m-blockers",
        current_version_id="vv-blockers",
        role_title="Senior Python Engineer",
        seniority_normalized="senior",
        budget_min=4000,
        budget_max=5000,
        budget_currency="USD",
        budget_period="month",
        work_format="remote",
        countries_allowed_json=["PL"],
        office_city=None,
        required_english_level="c1",
        has_take_home_task=False,
        take_home_paid=None,
        has_live_coding=False,
        hiring_stages_json=["recruiter_screen", "technical_interview", "final"],
        primary_tech_stack_json=["python", "postgresql"],
        project_description="Backend APIs for a hiring product.",
        questions_context_json={
            "matching_feedback": {
                "manager_feedback_events": [
                    {
                        "text": "These candidates keep missing on stack and English.",
                        "categories": ["stack", "english"],
                        "source_stage": "PRE_INTERVIEW_REVIEW",
                    }
                ]
            }
        },
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        vacancy,
        current_version=SimpleNamespace(
            id="vv-blockers",
            approval_summary_text="This vacancy is for a senior Python engineer.",
            summary_json={"approval_summary_text": "This vacancy is for a senior Python engineer."},
        ),
    )
    service.candidates = FakeCandidateProfilesRepository(
        [
            SimpleNamespace(
                id="cp-blockers",
                state="READY",
                salary_min=6500,
                country_code="PL",
                city="Warsaw",
                work_format="remote",
                seniority_normalized="middle",
                english_level="b1",
                show_take_home_task_roles=True,
                show_live_coding_roles=True,
            )
        ]
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m-blockers",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Why am I not seeing candidates yet?",
    )

    assert reply is not None
    lowered = reply.lower()
    assert "matching blockers" in lowered
    assert "salary floors are above the current budget" in lowered
    assert "english requirement is too high" in lowered
    assert "recent skip feedback" in lowered
    assert "stack and english level" in lowered


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


def test_graph_manager_stage_handles_jd_processing_question() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v2p", state="JD_PROCESSING")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m2p",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="?",
    )

    assert result is not None
    assert result.stage == "JD_PROCESSING"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None
    assert "summary" in result.reply_text.lower() or "process" in result.reply_text.lower()


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


def test_graph_manager_stage_does_not_treat_clarification_question_as_final_answer() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v3q", state="CLARIFICATION_QA")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m3q",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Gross or net budget?",
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


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


def test_graph_manager_stage_prefers_delete_confirmation_when_pending_on_non_latest_vacancy() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        [
            SimpleNamespace(
                id="v-old",
                state="OPEN",
                manager_user_id="m-del",
                questions_context_json={"deletion": {"pending": True}},
            ),
            SimpleNamespace(
                id="v-new",
                state="OPEN",
                manager_user_id="m-del",
                questions_context_json={},
            ),
        ]
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m-del",
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
        SimpleNamespace(
            id="v4",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "budget"},
        )
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


def test_graph_manager_stage_accepts_office_city_when_decision_returns_help(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_clarification_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": None,
                "proposed_action": None,
                "reason_code": "misclassified_help",
            }
        ),
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v4city",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "office_city"},
            work_format="hybrid",
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4city",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Warsaw",
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is True
    assert result.proposed_action == "send_vacancy_clarifications"
    assert result.structured_payload["office_city"] == "Warsaw"


def test_graph_manager_stage_accepts_cyrillic_english_level_when_decision_returns_help(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_clarification_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": None,
                "proposed_action": None,
                "reason_code": "misclassified_help",
            }
        ),
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v4english",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "english_level"},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4english",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="с1",
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is True
    assert result.proposed_action == "send_vacancy_clarifications"
    assert result.structured_payload["required_english_level"] == "c1"


def test_graph_manager_stage_accepts_take_home_only_when_decision_returns_help(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_clarification_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": None,
                "proposed_action": None,
                "reason_code": "misclassified_help",
            }
        ),
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v4assessment",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "assessment"},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4assessment",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="только тестовая таска",
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is True
    assert result.proposed_action == "send_vacancy_clarifications"
    assert result.structured_payload["has_take_home_task"] is True
    assert result.structured_payload["has_live_coding"] is False


def test_graph_manager_stage_accepts_free_take_home_payment_when_decision_returns_help(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_vacancy_clarification_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": None,
                "proposed_action": None,
                "reason_code": "misclassified_help",
            }
        ),
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v4payment",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "take_home_paid"},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4payment",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="бесплатная",
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is True
    assert result.proposed_action == "send_vacancy_clarifications"
    assert result.structured_payload["take_home_paid"] is False


def test_graph_manager_clarification_help_does_not_call_state_assistance(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.graph.stages.manager.safe_state_assistance_decision",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("state assistance should not run")),
    )

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v4help",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "budget"},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4help",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Gross or net budget?",
    )

    assert reply is not None


def test_graph_manager_stage_accepts_project_link_for_clarification() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(
            id="v4link",
            state="CLARIFICATION_QA",
            questions_context_json={"current_question_key": "project_description"},
        )
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m4link",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="https://repriced.ai",
    )

    assert result is not None
    assert result.stage == "CLARIFICATION_QA"
    assert result.action_accepted is True
    assert result.proposed_action == "send_vacancy_clarifications"
    assert result.structured_payload["project_description"] == "https://repriced.ai"


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


def test_graph_manager_stage_does_not_treat_open_status_question_as_delete() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v5q", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m5q",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="When will I see candidates?",
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


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
    assert result.reply_text is None


def test_graph_manager_stage_accepts_open_create_new_vacancy_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6c", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m6c",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Let's create another vacancy",
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is True
    assert result.proposed_action == "create_new_vacancy"
    assert result.stage_status == "ready_for_transition"
    assert result.reply_text is None


def test_graph_manager_stage_accepts_open_list_vacancies_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6l", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m6l",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Show my open vacancies",
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is True
    assert result.proposed_action == "list_open_vacancies"
    assert result.stage_status == "ready_for_transition"
    assert result.reply_text is None


def test_graph_manager_stage_accepts_find_matching_candidates_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6m", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m6m",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Find candidates for this vacancy",
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is True
    assert result.proposed_action == "find_matching_candidates"
    assert result.stage_status == "ready_for_transition"
    assert result.reply_text is None


def test_graph_manager_stage_accepts_open_vacancy_update_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6prefs", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m6prefs",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message=(
            "Update this vacancy: budget 7000-9000 USD, remote, English B2, no live coding, "
            "hiring stages recruiter screen, technical interview, final, project fintech platform, stack Python and FastAPI."
        ),
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is True
    assert result.proposed_action == "update_vacancy_preferences"
    assert result.stage_status == "ready_for_transition"
    assert result.structured_payload["budget_min"] == 7000
    assert result.structured_payload["budget_max"] == 9000
    assert result.structured_payload["work_format"] == "remote"
    assert result.structured_payload["required_english_level"] == "b2"
    assert result.structured_payload["has_live_coding"] is False
    assert result.structured_payload["hiring_stages_json"] == [
        "recruiter_screen",
        "technical_interview",
        "final",
    ]
    assert result.structured_payload["primary_tech_stack_json"][:2] == ["python", "fastapi"]


def test_graph_manager_stage_accepts_open_feedback_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6feedback", state="OPEN")
    )
    service.matches = FakeMatchingRepository()

    user = SimpleNamespace(
        id="m6feedback",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="These candidates feel weak on stack and English.",
    )

    assert result is not None
    assert result.stage == "OPEN"
    assert result.action_accepted is True
    assert result.proposed_action == "record_vacancy_feedback"
    assert result.stage_status == "ready_for_transition"
    assert result.structured_payload["feedback_text"] == "These candidates feel weak on stack and English."
    assert result.structured_payload["source_stage"] == "OPEN"


def test_graph_manager_stage_accepts_pre_interview_vacancy_update_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6pre", state="OPEN")
    )
    service.matches = FakeMatchingRepository(
        pre_interview_review_match=SimpleNamespace(id="m6pre", status="manager_decision_pending")
    )

    user = SimpleNamespace(
        id="m6pre",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Budget 7000-9000, B2 English, and no live coding.",
    )

    assert result is not None
    assert result.stage == "PRE_INTERVIEW_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "update_vacancy_preferences"
    assert result.stage_status == "ready_for_transition"
    assert result.structured_payload["budget_min"] == 7000
    assert result.structured_payload["budget_max"] == 9000
    assert result.structured_payload["required_english_level"] == "b2"
    assert result.structured_payload["has_live_coding"] is False


def test_graph_manager_stage_accepts_pre_interview_feedback_intent() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v6prefeedback", state="OPEN")
    )
    service.matches = FakeMatchingRepository(
        pre_interview_review_match=SimpleNamespace(id="m6prefeedback", status="manager_decision_pending")
    )

    user = SimpleNamespace(
        id="m6prefeedback",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="These candidates keep missing on stack and process.",
    )

    assert result is not None
    assert result.stage == "PRE_INTERVIEW_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "record_vacancy_feedback"
    assert result.stage_status == "ready_for_transition"
    assert result.structured_payload["feedback_text"] == "These candidates keep missing on stack and process."
    assert result.structured_payload["source_stage"] == "PRE_INTERVIEW_REVIEW"


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


def test_graph_manager_stage_help_receives_saved_evaluation_memory(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "src.graph.stages.manager.safe_manager_review_decision",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "intent": "help",
                "response_text": "Let me pull up the saved interview report.",
                "reason_code": "help",
            }
        ),
    )

    def _fake_assistance(_session, *, context, latest_user_message, recent_context=None):
        captured["context"] = context
        captured["latest_user_message"] = latest_user_message
        captured["recent_context"] = list(recent_context or [])
        return SimpleNamespace(payload={"response_text": "Here is the saved interview report.", "suggested_action": None})

    monkeypatch.setattr(
        "src.graph.stages.manager.safe_state_assistance_decision",
        _fake_assistance,
    )

    review_match = SimpleNamespace(id="m-eval", status="manager_review")

    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(SimpleNamespace(id="v-eval", state="OPEN"))
    service.matches = FakeMatchingRepository(manager_review_match=review_match)
    service.evaluations = FakeEvaluationsRepository(
        SimpleNamespace(
            match_id="m-eval",
            final_score=0.41,
            recommendation="reject",
            report_json={
                "interview_summary": "The candidate was experienced but missed several role-critical specifics.",
                "strengths": ["Good communication."],
                "risks": ["Weak role fit."],
                "recommendation": "reject",
                "final_score": 0.41,
            },
        )
    )

    user = SimpleNamespace(
        id="m-eval",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    reply = service.maybe_build_stage_reply(
        user=user,
        latest_user_message="Show me the interview summary and risks again.",
    )

    assert reply == "Here is the saved interview report."
    combined_context = " ".join(captured["recent_context"])
    assert "saved interview summary" in combined_context.lower()
    assert "role-critical specifics" in combined_context
    assert "saved evaluation risks" in combined_context.lower()
    assert "weak role fit" in combined_context.lower()
    assert "final score 0.41" in combined_context.lower()


def test_graph_manager_stage_does_not_treat_review_question_as_decision() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v7q", state="OPEN")
    )
    service.matches = FakeMatchingRepository(
        manager_review_match=SimpleNamespace(id="m1q", status="manager_review")
    )

    user = SimpleNamespace(
        id="m7q",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="What happens if I approve this candidate?",
    )

    assert result is not None
    assert result.stage == "MANAGER_REVIEW"
    assert result.action_accepted is False
    assert result.proposed_action is None
    assert result.reply_text is not None


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


def test_graph_manager_stage_accepts_manager_review_reject() -> None:
    service = LangGraphStageAgentService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.vacancies = FakeVacanciesRepository(
        SimpleNamespace(id="v8r", state="OPEN")
    )
    service.matches = FakeMatchingRepository(
        manager_review_match=SimpleNamespace(id="m2r", status="manager_review")
    )

    user = SimpleNamespace(
        id="m8r",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
        telegram_chat_id=200,
    )

    result = service.maybe_run_stage(
        user=user,
        latest_user_message="Reject candidate",
    )

    assert result is not None
    assert result.stage == "MANAGER_REVIEW"
    assert result.action_accepted is True
    assert result.proposed_action == "reject_candidate"
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
