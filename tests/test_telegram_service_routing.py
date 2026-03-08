from __future__ import annotations

from typing import Optional

from types import SimpleNamespace

from src.graph.service import StageAgentExecutionResult
from src.telegram.service import TelegramUpdateService
from src.telegram.types import NormalizedTelegramUpdate


class FakeNotificationsRepository:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)


class FakeMessagingService:
    def compose(self, approved_intent: str) -> str:
        return approved_intent

    def compose_role_selection(self, latest_user_message=None) -> str:
        return "Choose your role."


class FakeBotController:
    def __init__(self, response: Optional[str]):
        self.response = response
        self.calls = []

    def maybe_build_in_state_assistance(self, *, user, latest_user_message: str):
        self.calls.append({"user_id": user.id, "text": latest_user_message})
        return self.response

    def build_recovery_message(self, *, user, latest_user_message: str) -> str:
        return f"Recovery: {latest_user_message}"


class FakeStageAgentService:
    def __init__(
        self,
        response: Optional[str],
        entry_result: StageAgentExecutionResult | None = None,
        stage_result: StageAgentExecutionResult | None = None,
    ):
        self.response = response
        self.entry_result = entry_result
        self.stage_result = stage_result
        self.calls = []

    def maybe_build_entry_reply(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        self.calls.append(
            {
                "user_id": user.id,
                "text": latest_user_message,
                "message_type": latest_message_type,
            }
        )
        return self.response

    def maybe_run_entry_stage(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        self.calls.append(
            {
                "user_id": user.id,
                "text": latest_user_message,
                "message_type": latest_message_type,
                "kind": "entry_stage",
            }
        )
        if self.entry_result is not None:
            return self.entry_result
        if self.response is not None:
            return StageAgentExecutionResult(
                stage="CONTACT_REQUIRED",
                reply_text=self.response,
                stage_status="in_progress",
                proposed_action=None,
                action_accepted=False,
            )
        return None

    def maybe_build_stage_reply(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        self.calls.append(
            {
                "user_id": user.id,
                "text": latest_user_message,
                "message_type": latest_message_type,
                "kind": "stage",
            }
        )
        return self.response

    def maybe_run_stage(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        self.calls.append(
            {
                "user_id": user.id,
                "text": latest_user_message,
                "message_type": latest_message_type,
                "kind": "stage_execution",
            }
        )
        return self.stage_result


class FailIfCalledService:
    def __getattr__(self, item):
        def _fail(*args, **kwargs):
            raise AssertionError(f"{item} should not be called in this routing path")

        return _fail


class FakeCandidateService:
    def __init__(self):
        self.cv_calls = []
        self.verification_calls = []
        self.question_calls = []
        self.summary_calls = []
        self.deletion_calls = []
        self.start_calls = []
        self.summary_result = None
        self.deletion_result = None
        self.question_result = None
        self.verification_result = SimpleNamespace(
            notification_template="candidate_verification_instructions",
            notification_text="Please send the verification video.",
            status="instruction",
        )
        self.cv_result = SimpleNamespace(
            notification_template="candidate_cv_received_processing",
            status="accepted",
        )

    def handle_deletion_message(self, **kwargs):
        self.deletion_calls.append(kwargs)
        return self.deletion_result

    def start_onboarding(self, user, trigger_ref_id):
        self.start_calls.append({"user": user, "trigger_ref_id": trigger_ref_id})

    def handle_summary_review_action(self, **kwargs):
        self.summary_calls.append(kwargs)
        return self.summary_result

    def handle_questions_answer(self, **kwargs):
        self.question_calls.append(kwargs)
        return self.question_result

    def handle_questions_parsed_payload(self, **kwargs):
        self.question_calls.append(kwargs)
        return self.question_result

    def handle_cv_intake(self, **kwargs):
        self.cv_calls.append(kwargs)
        return self.cv_result

    def handle_verification_submission(self, **kwargs):
        self.verification_calls.append(kwargs)
        return self.verification_result


class FakeVacancyService:
    def __init__(self):
        self.intake_calls = []
        self.clarification_calls = []
        self.deletion_calls = []
        self.start_calls = []
        self.deletion_result = None
        self.clarification_result = None

    def handle_deletion_message(self, **kwargs):
        self.deletion_calls.append(kwargs)
        return self.deletion_result

    def start_onboarding(self, user, trigger_ref_id):
        self.start_calls.append({"user": user, "trigger_ref_id": trigger_ref_id})

    def handle_clarification_answer(self, **kwargs):
        self.clarification_calls.append(kwargs)
        return self.clarification_result

    def handle_clarification_parsed_payload(self, **kwargs):
        self.clarification_calls.append(kwargs)
        return self.clarification_result

    def handle_jd_intake(self, **kwargs):
        self.intake_calls.append(kwargs)
        return SimpleNamespace(
            notification_template="vacancy_jd_received_processing",
            status="accepted",
        )


class FakeEvaluationService:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(
            status="help",
            notification_template="manager_candidate_review_help",
            notification_text="Reply 'Approve candidate' or 'Reject candidate'.",
        )

    def handle_manager_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeInterviewService:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(
            status="invite_pending",
            notification_template="candidate_interview_invitation_help",
            notification_text="Reply 'Accept interview' or 'Skip opportunity'.",
        )

    def handle_candidate_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeIdentityService:
    def __init__(self, *, consent: bool = False):
        self.consent = consent
        self.attach_calls = []
        self.grant_calls = []
        self.set_role_calls = []

    def attach_contact(self, user, normalized_update):
        self.attach_calls.append({"user": user, "update": normalized_update})
        user.phone_number = normalized_update.contact_phone_number

    def has_data_processing_consent(self, user):
        return self.consent

    def grant_data_processing_consent(self, user, source_raw_message_id):
        self.grant_calls.append({"user": user, "source_raw_message_id": source_raw_message_id})
        self.consent = True

    def set_role(self, user, role):
        self.set_role_calls.append({"user": user, "role": role})
        user.is_candidate = role == "candidate"
        user.is_hiring_manager = role == "hiring_manager"


def build_update(
    *,
    text: Optional[str] = None,
    content_type: str = "text",
    contact_phone_number: Optional[str] = None,
) -> NormalizedTelegramUpdate:
    return NormalizedTelegramUpdate(
        update_id=1,
        telegram_user_id=100,
        telegram_chat_id=200,
        message_id=300,
        content_type=content_type,
        text=text,
        contact_phone_number=contact_phone_number,
        display_name="Test User",
        username="testuser",
        language_code="en",
        file=None,
        payload={},
    )


def build_service() -> TelegramUpdateService:
    service = TelegramUpdateService(session=object())
    service.notifications_repo = FakeNotificationsRepository()
    service.messaging = FakeMessagingService()
    service.stage_agents = FakeStageAgentService(None)
    return service


def test_start_without_contact_requests_contact() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g1",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g1", build_update(text="/start"))

    assert templates == ["request_contact"]
    assert service.notifications_repo.calls[-1]["template_key"] == "request_contact"
    assert service.notifications_repo.calls[-1]["payload_json"]["reply_markup"] is not None


def test_contact_required_help_intercepts_before_identity_gating() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)
    service.stage_agents = FakeStageAgentService("Please use the contact button so Helly can continue onboarding.")
    service.bot_controller = FakeBotController(None)

    user = SimpleNamespace(
        id="g1h",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g1h", build_update(text="Why do you need my contact?"))

    assert templates == ["request_contact"]
    assert service.stage_agents.calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_contact"


def test_contact_required_help_falls_back_to_old_controller_if_graph_returns_none() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)
    service.stage_agents = FakeStageAgentService(None)
    service.bot_controller = FakeBotController("Fallback contact guidance.")

    user = SimpleNamespace(
        id="g1hf",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g1hf", build_update(text="Why?"))

    assert templates == ["state_aware_help"]
    assert service.stage_agents.calls
    assert service.bot_controller.calls
    assert service.notifications_repo.calls[-1]["payload_json"]["text"] == "Fallback contact guidance."


def test_start_with_contact_but_without_consent_requests_consent() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g2", build_update(text="/start"))

    assert templates == ["request_consent"]
    assert service.notifications_repo.calls[-1]["template_key"] == "request_consent"
    assert service.notifications_repo.calls[-1]["payload_json"]["reply_markup"] is not None


def test_consent_required_help_intercepts_before_identity_gating() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)
    service.stage_agents = FakeStageAgentService(
        None,
        entry_result=StageAgentExecutionResult(
            stage="CONSENT_REQUIRED",
            reply_text="Helly needs consent before storing profile data.",
            stage_status="in_progress",
            proposed_action=None,
            action_accepted=False,
        ),
    )

    user = SimpleNamespace(
        id="g2h",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g2h", build_update(text="Why do you need my consent?"))

    assert templates == ["request_consent"]
    assert service.notifications_repo.calls[-1]["template_key"] == "request_consent"


def test_start_with_contact_and_consent_requests_role() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)

    user = SimpleNamespace(
        id="g3",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g3", build_update(text="/start"))

    assert templates == ["request_role"]
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"
    assert service.notifications_repo.calls[-1]["payload_json"]["reply_markup"] is not None


def test_role_selection_help_intercepts_before_identity_gating() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)
    service.stage_agents = FakeStageAgentService(
        None,
        entry_result=StageAgentExecutionResult(
            stage="ROLE_SELECTION",
            reply_text="Choose Candidate if you are job searching, or Hiring Manager if you want to hire.",
            stage_status="in_progress",
            proposed_action=None,
            action_accepted=False,
        ),
    )

    user = SimpleNamespace(
        id="g3h",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g3h", build_update(text="Why do I need to choose my role?"))

    assert templates == ["request_role"]
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"


def test_contact_share_without_consent_requests_consent() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g4",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw-g4",
        build_update(contact_phone_number="+380974527344"),
    )

    assert templates == ["request_consent"]
    assert service.identity_service.attach_calls
    assert user.phone_number == "+380974527344"


def test_contact_share_with_existing_consent_requests_role() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)

    user = SimpleNamespace(
        id="g4a",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw-g4a",
        build_update(contact_phone_number="+380974527345"),
    )

    assert templates == ["request_role"]
    assert service.identity_service.attach_calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"


def test_consent_message_grants_consent_and_requests_role() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g4b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g4b", build_update(text="I agree"))

    assert templates == ["request_role"]
    assert service.identity_service.grant_calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"


def test_agree_alias_grants_consent_and_requests_role() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g4d",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g4d", build_update(text="agree"))

    assert templates == ["request_role"]
    assert service.identity_service.grant_calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"


def test_consent_alias_grants_consent_and_requests_role() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g4e",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g4e", build_update(text="consent"))

    assert templates == ["request_role"]
    assert service.identity_service.grant_calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"


def test_consent_with_punctuation_grants_consent_and_requests_role() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g4f",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g4f", build_update(text="I agree."))

    assert templates == ["request_role"]
    assert service.identity_service.grant_calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_role"


def test_consent_before_contact_requests_contact() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)

    user = SimpleNamespace(
        id="g4c",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g4c", build_update(text="I agree"))

    assert templates == ["request_contact"]
    assert not service.identity_service.grant_calls
    assert service.notifications_repo.calls[-1]["template_key"] == "request_contact"


def test_role_selection_before_contact_requests_contact_and_blocks_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="g5",
        phone_number=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5", build_update(text="Candidate"))

    assert templates == ["request_contact"]
    assert not service.candidate_service.start_calls
    assert not service.vacancy_service.start_calls


def test_role_selection_without_consent_requests_consent_and_blocks_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="g5a",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5a", build_update(text="Candidate"))

    assert templates == ["request_consent"]
    assert not service.candidate_service.start_calls
    assert not service.vacancy_service.start_calls


def test_candidate_role_selection_starts_candidate_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="g5b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5b", build_update(text="Candidate"))

    assert templates == ["candidate_onboarding_started"]
    assert service.identity_service.set_role_calls[-1]["role"] == "candidate"
    assert service.candidate_service.start_calls
    assert not service.vacancy_service.start_calls


def test_graph_entry_stage_can_grant_consent() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=False)
    service.stage_agents = FakeStageAgentService(
        None,
        entry_result=StageAgentExecutionResult(
            stage="CONSENT_REQUIRED",
            reply_text="Thanks. I will record your consent and move to role selection.",
            stage_status="ready_for_transition",
            proposed_action="reply_i_agree",
            action_accepted=True,
            validation_result={"accepted": True, "normalized_action": "reply_i_agree"},
        ),
    )

    user = SimpleNamespace(
        id="g4x",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g4x", build_update(text="I agree"))

    assert templates == ["request_role"]
    assert service.identity_service.grant_calls


def test_graph_entry_stage_can_start_candidate_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()
    service.stage_agents = FakeStageAgentService(
        None,
        entry_result=StageAgentExecutionResult(
            stage="ROLE_SELECTION",
            reply_text="Understood. I will start the candidate flow.",
            stage_status="ready_for_transition",
            proposed_action="candidate",
            action_accepted=True,
            structured_payload={"role": "candidate"},
            validation_result={"accepted": True, "normalized_action": "candidate"},
        ),
    )

    user = SimpleNamespace(
        id="g5x",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5x", build_update(text="Candidate"))

    assert templates == ["candidate_onboarding_started"]
    assert service.identity_service.set_role_calls[-1]["role"] == "candidate"
    assert service.candidate_service.start_calls


def test_uppercase_candidate_role_selection_starts_candidate_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="g5bb",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5bb", build_update(text="CANDIDATE"))

    assert templates == ["candidate_onboarding_started"]
    assert service.identity_service.set_role_calls[-1]["role"] == "candidate"
    assert service.candidate_service.start_calls


def test_manager_role_selection_starts_manager_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="g5c",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5c", build_update(text="Hiring Manager"))

    assert templates == ["manager_onboarding_started"]
    assert service.identity_service.set_role_calls[-1]["role"] == "hiring_manager"
    assert service.vacancy_service.start_calls
    assert not service.candidate_service.start_calls


def test_uppercase_manager_role_selection_starts_manager_onboarding() -> None:
    service = build_service()
    service.identity_service = FakeIdentityService(consent=True)
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="g5cc",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw-g5cc", build_update(text="HIRING MANAGER"))

    assert templates == ["manager_onboarding_started"]
    assert service.identity_service.set_role_calls[-1]["role"] == "hiring_manager"
    assert service.vacancy_service.start_calls


def test_candidate_cv_help_is_intercepted_before_cv_intake() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "No problem. You can paste your experience as text, send a voice note, or upload a LinkedIn PDF."
    )
    service.bot_controller = FakeBotController(
        "Old fallback should not be used."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u1",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw1", build_update(text="I do not have a CV yet."))

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls
    assert not service.candidate_service.cv_calls


def test_candidate_cv_short_help_question_is_intercepted_before_cv_intake() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "No problem. You can paste your experience as text, send a voice note, or upload a LinkedIn PDF."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u1short",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw1short", build_update(text="If I don't have?"))

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert not service.candidate_service.cv_calls


def test_candidate_cv_passthrough_reaches_cv_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = None
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = None
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u1a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw1a",
        build_update(text="Senior backend engineer with 7 years in Python, Go, AWS, and PostgreSQL."),
    )

    assert templates == ["candidate_cv_received_processing"]
    assert service.candidate_service.cv_calls


def test_graph_cv_stage_can_own_text_cv_completion() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="CV_PENDING",
            reply_text="Thanks. I will use this experience summary to prepare your profile.",
            stage_status="ready_for_transition",
            proposed_action="send_cv_text",
            action_accepted=True,
            structured_payload={"cv_text": "Senior backend engineer with 7 years in Python"},
            validation_result={"accepted": True, "normalized_action": "send_cv_text"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = None
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = None
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u1ax",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw1ax",
        build_update(text="Senior backend engineer with 7 years in Python"),
    )

    assert templates == ["candidate_cv_received_processing"]
    assert service.candidate_service.cv_calls
    assert service.candidate_service.cv_calls[-1]["text"] == "Senior backend engineer with 7 years in Python"


def test_candidate_voice_cv_passthrough_reaches_cv_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = None
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = None
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u1b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw1b",
        build_update(content_type="voice"),
    )

    assert templates == ["candidate_cv_received_processing"]
    assert service.candidate_service.cv_calls


def test_candidate_document_cv_passthrough_reaches_cv_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = None
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = None
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u1c",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw1c",
        build_update(content_type="document"),
    )

    assert templates == ["candidate_cv_received_processing"]
    assert service.candidate_service.cv_calls


def test_manager_jd_help_is_intercepted_before_jd_intake() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "Yes. You can paste the role title, stack, seniority, budget, and work format as plain text."
    )
    service.bot_controller = FakeBotController(
        "Old manager intake fallback should not be used."
    )
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()

    user = SimpleNamespace(
        id="u2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(user, "raw2", build_update(text="Can I just paste the job details here?"))

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls
    assert not service.vacancy_service.intake_calls


def test_manager_jd_passthrough_reaches_jd_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = None

    user = SimpleNamespace(
        id="u2a",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw2a",
        build_update(text="Senior Python engineer, fintech product, remote in Europe, budget 6000 EUR."),
    )

    assert templates == ["vacancy_jd_received_processing"]
    assert service.vacancy_service.intake_calls


def test_graph_manager_intake_stage_can_own_text_jd_completion() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="INTAKE_PENDING",
            reply_text="Thanks. I will use this job description to prepare the vacancy draft.",
            stage_status="ready_for_transition",
            proposed_action="send_job_description_text",
            action_accepted=True,
            structured_payload={
                "job_description_text": "Senior Python engineer, fintech product, remote in Europe, budget 6000 EUR."
            },
            validation_result={"accepted": True, "normalized_action": "send_job_description_text"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = None

    user = SimpleNamespace(
        id="u2ax",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw2ax",
        build_update(text="Senior Python engineer, fintech product, remote in Europe, budget 6000 EUR."),
    )

    assert templates == ["vacancy_jd_received_processing"]
    assert service.vacancy_service.intake_calls
    assert (
        service.vacancy_service.intake_calls[-1]["text"]
        == "Senior Python engineer, fintech product, remote in Europe, budget 6000 EUR."
    )


def test_manager_voice_jd_passthrough_reaches_jd_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = None

    user = SimpleNamespace(
        id="u2b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw2b",
        build_update(content_type="voice"),
    )

    assert templates == ["vacancy_jd_received_processing"]
    assert service.vacancy_service.intake_calls


def test_manager_video_jd_passthrough_reaches_jd_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = None

    user = SimpleNamespace(
        id="u2c",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw2c",
        build_update(content_type="video"),
    )

    assert templates == ["vacancy_jd_received_processing"]
    assert service.vacancy_service.intake_calls


def test_candidate_verification_help_is_intercepted_before_submission_handler() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "You can do the verification later from a device with a camera. The step cannot be skipped."
    )
    service.bot_controller = FakeBotController(
        "Old verification fallback should not be used."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u3",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw3",
        build_update(text="I cannot record video now because I am on desktop."),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls
    assert not service.candidate_service.verification_calls


def test_candidate_questions_help_is_intercepted_before_questions_handler() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "I need salary, location, and work format so Helly can apply matching filters correctly."
    )
    service.bot_controller = FakeBotController(
        "Old questions fallback should not be used."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4",
        build_update(text="Why do you need my salary and location?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls


def test_summary_review_help_is_intercepted_before_summary_handler() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "Tell me exactly what is wrong in the summary, and I will revise it once."
    )
    service.bot_controller = FakeBotController(
        "Old summary fallback should not be used."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4a",
        build_update(text="What should I change in this summary if something is wrong?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls
    assert not service.candidate_service.summary_calls


def test_summary_review_actual_correction_reaches_summary_handler() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="SUMMARY_REVIEW",
            reply_text="Thanks. I will update the summary based on your correction.",
            stage_status="ready_for_transition",
            proposed_action="request_summary_change",
            action_accepted=True,
            structured_payload={"edit_text": "The summary is wrong: I work mostly with Go, not Python."},
            validation_result={"accepted": True, "normalized_action": "request_summary_change"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_edit_processing",
        status="processing",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.calls = []
    service.interview_service.handle_candidate_message = lambda **kwargs: None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4b",
        build_update(text="The summary is wrong: I work mostly with Go, not Python."),
    )

    assert templates == ["candidate_summary_edit_processing"]
    assert service.candidate_service.summary_calls


def test_summary_review_approve_passthrough_reaches_summary_handler() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="SUMMARY_REVIEW",
            reply_text="Thanks. I will approve the summary and move to the next step.",
            stage_status="ready_for_transition",
            proposed_action="approve_summary",
            action_accepted=True,
            validation_result={"accepted": True, "normalized_action": "approve_summary"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_approved",
        status="approved",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4c",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4c",
        build_update(text="Approve summary"),
    )

    assert templates == ["candidate_summary_approved"]
    assert service.candidate_service.summary_calls


def test_summary_review_approve_with_whitespace_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_approved",
        status="approved",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4c1",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4c1",
        build_update(text="  Approve summary  "),
    )

    assert templates == ["candidate_summary_approved"]
    assert service.candidate_service.summary_calls


def test_summary_review_uppercase_approve_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_approved",
        status="approved",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4c2",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4c2",
        build_update(text="APPROVE SUMMARY"),
    )

    assert templates == ["candidate_summary_approved"]
    assert service.candidate_service.summary_calls


def test_summary_review_approve_with_punctuation_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_approved",
        status="approved",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4c3",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4c3",
        build_update(text="Approve summary."),
    )

    assert templates == ["candidate_summary_approved"]
    assert service.candidate_service.summary_calls


def test_summary_review_approve_profile_alias_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_approved",
        status="approved",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4d",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4d",
        build_update(text="Approve profile"),
    )

    assert templates == ["candidate_summary_approved"]
    assert service.candidate_service.summary_calls


def test_summary_review_edit_alias_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_edit_empty",
        status="awaiting_edit_details",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4e",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4e",
        build_update(text="Edit summary"),
    )

    assert templates == ["candidate_summary_edit_empty"]
    assert service.candidate_service.summary_calls


def test_summary_review_edit_with_punctuation_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_edit_empty",
        status="awaiting_edit_details",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4e1",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4e1",
        build_update(text="Edit summary."),
    )

    assert templates == ["candidate_summary_edit_empty"]
    assert service.candidate_service.summary_calls


def test_summary_review_change_summary_alias_reaches_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.summary_result = SimpleNamespace(
        notification_template="candidate_summary_edit_empty",
        status="awaiting_edit_details",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u4f",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw4f",
        build_update(text="Change summary"),
    )

    assert templates == ["candidate_summary_edit_empty"]
    assert service.candidate_service.summary_calls


def test_candidate_ready_help_is_intercepted_before_fallback() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "Your profile is ready. Helly will contact you when a strong match is found."
    )
    service.bot_controller = FakeBotController(
        "Old ready fallback should not be used."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u5",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw5",
        build_update(text="What should I do next?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls


def test_graph_ready_stage_can_own_delete_profile_intent() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="READY",
            reply_text="I can help you remove the profile if you want to stop using Helly.",
            stage_status="ready_for_transition",
            proposed_action="delete_profile",
            action_accepted=True,
            structured_payload={},
            validation_result={"accepted": True, "normalized_action": "delete_profile"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="confirmation_required",
        notification_template="candidate_deletion_confirmation_required",
        notification_text="Please confirm profile deletion.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u5a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw5a",
        build_update(text="Delete profile"),
    )

    assert templates == ["candidate_deletion_confirmation_required"]
    assert service.candidate_service.deletion_calls
    assert service.candidate_service.deletion_calls[-1]["text"] == "delete profile"


def test_interview_invite_help_is_intercepted_before_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "The interview is short and you can answer in text, voice, or video."
    )
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u6",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw6",
        build_update(text="How long does the interview take and can I answer by voice?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert not service.interview_service.calls


def test_candidate_delete_confirmation_help_is_intercepted_after_delete_prompt() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "If you confirm deletion, the profile will be removed from active recruiting flow and active interviews or matches may be cancelled."
    )
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = None
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u6a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw6a",
        build_update(text="What exactly will be cancelled if I confirm?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.candidate_service.deletion_calls


def test_vacancy_delete_confirmation_help_is_intercepted_after_delete_prompt() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "If you confirm deletion, the vacancy will be removed from active flow and related interviews or matches may be cancelled."
    )
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = None
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u6b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw6b",
        build_update(text="Can I cancel this instead of deleting the vacancy?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.vacancy_service.deletion_calls


def test_manager_review_help_is_intercepted_before_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "The evaluation summarizes strengths, risks, and recommendation before you approve or reject."
    )
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()

    user = SimpleNamespace(
        id="u7",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw7",
        build_update(text="What do these scores mean before I approve or reject?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert not service.evaluation_service.calls


def test_manager_approve_passthrough_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="approved",
        notification_template="manager_candidate_approved",
        notification_text="Candidate approved.",
    )

    user = SimpleNamespace(
        id="u8",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw8",
        build_update(text="Approve candidate"),
    )

    assert templates == ["manager_candidate_approved"]
    assert service.evaluation_service.calls


def test_manager_approve_alias_passthrough_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="approved",
        notification_template="manager_candidate_approved",
        notification_text="Candidate approved.",
    )

    user = SimpleNamespace(
        id="u8a",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw8a",
        build_update(text="Approve"),
    )

    assert templates == ["manager_candidate_approved"]
    assert service.evaluation_service.calls


def test_manager_uppercase_approve_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="approved",
        notification_template="manager_candidate_approved",
        notification_text="Candidate approved.",
    )

    user = SimpleNamespace(
        id="u8b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw8b",
        build_update(text="APPROVE"),
    )

    assert templates == ["manager_candidate_approved"]
    assert service.evaluation_service.calls


def test_manager_approve_with_punctuation_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="approved",
        notification_template="manager_candidate_approved",
        notification_text="Candidate approved.",
    )

    user = SimpleNamespace(
        id="u8c",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw8c",
        build_update(text="Approve."),
    )

    assert templates == ["manager_candidate_approved"]
    assert service.evaluation_service.calls


def test_interview_accept_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="accepted",
        notification_template="candidate_interview_started",
        notification_text="Interview started.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u9",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw9",
        build_update(text="Accept interview"),
    )

    assert templates == ["candidate_interview_started"]
    assert service.interview_service.calls


def test_graph_interview_invited_stage_can_own_accept() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="INTERVIEW_INVITED",
            reply_text="Thanks. I will start the interview.",
            stage_status="ready_for_transition",
            proposed_action="accept_interview",
            action_accepted=True,
            structured_payload={},
            validation_result={"accepted": True, "normalized_action": "accept_interview"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="accepted",
        notification_template="candidate_interview_started",
        notification_text="Interview started.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u9x",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw9x",
        build_update(text="Accept interview"),
    )

    assert templates == ["candidate_interview_started"]
    assert service.interview_service.calls
    assert service.interview_service.calls[-1]["text"] == "Accept interview"


def test_interview_accept_alias_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="accepted",
        notification_template="candidate_interview_started",
        notification_text="Interview started.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u9a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw9a",
        build_update(text="Accept"),
    )

    assert templates == ["candidate_interview_started"]
    assert service.interview_service.calls


def test_interview_uppercase_accept_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="accepted",
        notification_template="candidate_interview_started",
        notification_text="Interview started.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u9b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw9b",
        build_update(text="ACCEPT"),
    )

    assert templates == ["candidate_interview_started"]
    assert service.interview_service.calls


def test_interview_accept_with_punctuation_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="accepted",
        notification_template="candidate_interview_started",
        notification_text="Interview started.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u9c",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw9c",
        build_update(text="Accept!"),
    )

    assert templates == ["candidate_interview_started"]
    assert service.interview_service.calls


def test_interview_skip_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="skipped",
        notification_template="candidate_interview_skipped",
        notification_text="Opportunity skipped.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10",
        build_update(text="Skip opportunity"),
    )

    assert templates == ["candidate_interview_skipped"]
    assert service.interview_service.calls


def test_graph_interview_invited_stage_can_own_skip() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="INTERVIEW_INVITED",
            reply_text="Understood. I will skip this opportunity.",
            stage_status="ready_for_transition",
            proposed_action="skip_opportunity",
            action_accepted=True,
            structured_payload={},
            validation_result={"accepted": True, "normalized_action": "skip_opportunity"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="skipped",
        notification_template="candidate_interview_skipped",
        notification_text="Opportunity skipped.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10x",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10x",
        build_update(text="Skip opportunity"),
    )

    assert templates == ["candidate_interview_skipped"]
    assert service.interview_service.calls
    assert service.interview_service.calls[-1]["text"] == "Skip opportunity"


def test_interview_skip_alias_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="skipped",
        notification_template="candidate_interview_skipped",
        notification_text="Opportunity skipped.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10aa",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10aa",
        build_update(text="Skip"),
    )

    assert templates == ["candidate_interview_skipped"]
    assert service.interview_service.calls


def test_interview_skip_with_punctuation_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="skipped",
        notification_template="candidate_interview_skipped",
        notification_text="Opportunity skipped.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10ab",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10ab",
        build_update(text="Skip!"),
    )

    assert templates == ["candidate_interview_skipped"]
    assert service.interview_service.calls


def test_interview_answer_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="processing",
        notification_template="candidate_interview_answer_processing",
        notification_text="Answer received.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10c",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10c",
        build_update(text="In that project I designed the API boundary and owned the background job pipeline."),
    )

    assert templates == ["candidate_interview_answer_processing"]
    assert service.interview_service.calls


def test_interview_voice_answer_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="processing",
        notification_template="candidate_interview_answer_processing",
        notification_text="Voice answer received.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10d",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10d",
        build_update(content_type="voice"),
    )

    assert templates == ["candidate_interview_answer_processing"]
    assert service.interview_service.calls


def test_interview_video_answer_passthrough_reaches_interview_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = SimpleNamespace(
        status="processing",
        notification_template="candidate_interview_answer_processing",
        notification_text="Video answer received.",
    )
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10e",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10e",
        build_update(content_type="video"),
    )

    assert templates == ["candidate_interview_answer_processing"]
    assert service.interview_service.calls


def test_candidate_questions_answer_passthrough_reaches_questions_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = SimpleNamespace(
        status="needs_followup",
        notification_template="candidate_questions_followup",
        notification_text="Please confirm whether you prefer remote, hybrid, or office work.",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10a",
        build_update(text="I expect 4000 USD and I am based in Warsaw."),
    )

    assert templates == ["candidate_questions_followup"]
    assert service.candidate_service.question_calls


def test_graph_questions_stage_can_own_text_questions_completion() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="QUESTIONS_PENDING",
            reply_text="Thanks. I will update your profile details from this answer.",
            stage_status="ready_for_transition",
            proposed_action="send_salary_location_work_format",
            action_accepted=True,
            structured_payload={
                "salary_min": 4000,
                "salary_max": 4000,
                "salary_currency": "USD",
                "location_text": "Warsaw",
            },
            validation_result={"accepted": True, "normalized_action": "send_salary_location_work_format"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = SimpleNamespace(
        status="needs_followup",
        notification_template="candidate_questions_followup",
        notification_text="Please confirm whether you prefer remote, hybrid, or office work.",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10ax",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10ax",
        build_update(text="I expect 4000 USD and I am based in Warsaw."),
    )

    assert templates == ["candidate_questions_followup"]
    assert service.candidate_service.question_calls
    assert service.candidate_service.question_calls[-1]["parsed_payload"]["salary_min"] == 4000


def test_candidate_questions_voice_answer_passthrough_reaches_questions_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.verification_result = None
    service.candidate_service.question_result = SimpleNamespace(
        status="needs_followup",
        notification_template="candidate_questions_followup",
        notification_text="Please confirm your preferred work format.",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10f",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10f",
        build_update(content_type="voice"),
    )

    assert templates == ["candidate_questions_followup"]
    assert service.candidate_service.question_calls


def test_candidate_verification_video_passthrough_reaches_verification_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.verification_result = SimpleNamespace(
        status="ready",
        notification_template="candidate_ready",
        notification_text="Profile ready.",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10b",
        build_update(content_type="video"),
    )

    assert templates == ["candidate_ready"]
    assert service.candidate_service.verification_calls


def test_graph_verification_stage_can_own_video_submission() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="VERIFICATION_PENDING",
            reply_text="Thanks. I will use this video to complete your verification step.",
            stage_status="ready_for_transition",
            proposed_action="send_verification_video",
            action_accepted=True,
            structured_payload={"submission_type": "video"},
            validation_result={"accepted": True, "normalized_action": "send_verification_video"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.verification_result = SimpleNamespace(
        status="ready",
        notification_template="candidate_ready",
        notification_text="Profile ready.",
    )
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u10bv",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw10bv",
        build_update(content_type="video"),
        file_id="file-1",
    )

    assert templates == ["candidate_ready"]
    assert service.candidate_service.verification_calls
    assert service.candidate_service.verification_calls[-1]["content_type"] == "video"


def test_candidate_delete_confirm_passthrough_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="candidate_deleted",
        notification_text="Profile deleted.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11",
        build_update(text="Confirm delete profile"),
    )

    assert templates == ["candidate_deleted"]
    assert service.candidate_service.deletion_calls


def test_candidate_generic_confirm_delete_alias_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="candidate_deleted",
        notification_text="Profile deleted.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11c",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11c",
        build_update(text="Confirm delete"),
    )

    assert templates == ["candidate_deleted"]
    assert service.candidate_service.deletion_calls


def test_candidate_confirm_delete_with_whitespace_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="candidate_deleted",
        notification_text="Profile deleted.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11c1",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11c1",
        build_update(text="  Confirm delete profile  "),
    )

    assert templates == ["candidate_deleted"]
    assert service.candidate_service.deletion_calls


def test_candidate_uppercase_confirm_delete_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="candidate_deleted",
        notification_text="Profile deleted.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11c2",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11c2",
        build_update(text="CONFIRM DELETE PROFILE"),
    )

    assert templates == ["candidate_deleted"]
    assert service.candidate_service.deletion_calls


def test_candidate_confirm_delete_with_punctuation_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="candidate_deleted",
        notification_text="Profile deleted.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11c3",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11c3",
        build_update(text="Confirm delete profile."),
    )

    assert templates == ["candidate_deleted"]
    assert service.candidate_service.deletion_calls


def test_candidate_delete_cancel_passthrough_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="cancelled",
        notification_template="candidate_deletion_cancelled",
        notification_text="Profile deletion cancelled.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11a",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11a",
        build_update(text="Cancel delete"),
    )

    assert templates == ["candidate_deletion_cancelled"]
    assert service.candidate_service.deletion_calls


def test_candidate_keep_profile_alias_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="cancelled",
        notification_template="candidate_deletion_cancelled",
        notification_text="Profile deletion cancelled.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11d",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11d",
        build_update(text="Keep profile"),
    )

    assert templates == ["candidate_deletion_cancelled"]
    assert service.candidate_service.deletion_calls


def test_candidate_dont_delete_alias_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.candidate_service.deletion_result = SimpleNamespace(
        status="cancelled",
        notification_template="candidate_deletion_cancelled",
        notification_text="Profile deletion cancelled.",
    )
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FailIfCalledService()
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u11b",
        phone_number="+123",
        is_candidate=True,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw11b",
        build_update(text="don't delete"),
    )

    assert templates == ["candidate_deletion_cancelled"]
    assert service.candidate_service.deletion_calls


def test_vacancy_delete_confirm_passthrough_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="vacancy_deleted",
        notification_text="Vacancy deleted.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12",
        build_update(text="Confirm delete vacancy"),
    )

    assert templates == ["vacancy_deleted"]
    assert service.vacancy_service.deletion_calls


def test_vacancy_generic_confirm_delete_alias_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="vacancy_deleted",
        notification_text="Vacancy deleted.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12f",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12f",
        build_update(text="Confirm delete"),
    )

    assert templates == ["vacancy_deleted"]
    assert service.vacancy_service.deletion_calls


def test_vacancy_confirm_delete_with_whitespace_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="vacancy_deleted",
        notification_text="Vacancy deleted.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12f1",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12f1",
        build_update(text="  Confirm delete vacancy  "),
    )

    assert templates == ["vacancy_deleted"]
    assert service.vacancy_service.deletion_calls


def test_vacancy_uppercase_confirm_delete_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="vacancy_deleted",
        notification_text="Vacancy deleted.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12f2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12f2",
        build_update(text="CONFIRM DELETE VACANCY"),
    )

    assert templates == ["vacancy_deleted"]
    assert service.vacancy_service.deletion_calls


def test_vacancy_confirm_delete_with_punctuation_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="deleted",
        notification_template="vacancy_deleted",
        notification_text="Vacancy deleted.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12f3",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12f3",
        build_update(text="Confirm delete vacancy."),
    )

    assert templates == ["vacancy_deleted"]
    assert service.vacancy_service.deletion_calls


def test_vacancy_delete_cancel_passthrough_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="cancelled",
        notification_template="vacancy_deletion_cancelled",
        notification_text="Vacancy deletion cancelled.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12c",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12c",
        build_update(text="Cancel delete"),
    )

    assert templates == ["vacancy_deletion_cancelled"]
    assert service.vacancy_service.deletion_calls


def test_vacancy_keep_vacancy_alias_reaches_deletion_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="cancelled",
        notification_template="vacancy_deletion_cancelled",
        notification_text="Vacancy deletion cancelled.",
    )
    service.evaluation_service = FailIfCalledService()

    user = SimpleNamespace(
        id="u12g",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12g",
        build_update(text="Keep vacancy"),
    )

    assert templates == ["vacancy_deletion_cancelled"]
    assert service.vacancy_service.deletion_calls


def test_manager_clarification_answer_passthrough_reaches_clarification_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = SimpleNamespace(
        status="open",
        notification_template="vacancy_open",
        notification_text="Vacancy is now open.",
    )
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u12a",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12a",
        build_update(text="Budget is 5000 to 7000 USD, remote across Poland and Germany."),
    )

    assert templates == ["vacancy_open"]
    assert service.vacancy_service.clarification_calls


def test_graph_manager_clarification_stage_can_own_text_completion() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="CLARIFICATION_QA",
            reply_text="Thanks. I will update the vacancy details from this answer.",
            stage_status="ready_for_transition",
            proposed_action="send_vacancy_clarifications",
            action_accepted=True,
            structured_payload={
                "budget_min": 5000,
                "budget_max": 7000,
                "budget_currency": "USD",
                "work_format": "remote",
                "countries_allowed_json": ["PL", "DE"],
            },
            validation_result={"accepted": True, "normalized_action": "send_vacancy_clarifications"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = SimpleNamespace(
        status="open",
        notification_template="vacancy_open",
        notification_text="Vacancy is now open.",
    )
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u12ax",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12ax",
        build_update(text="Budget is 5000 to 7000 USD, remote across Poland and Germany."),
    )

    assert templates == ["vacancy_open"]
    assert service.vacancy_service.clarification_calls
    assert service.vacancy_service.clarification_calls[-1]["parsed_payload"]["budget_min"] == 5000


def test_manager_open_help_is_intercepted_before_fallback() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        "Your vacancy is open. Helly is matching candidates and will send qualified profiles."
    )
    service.bot_controller = FakeBotController("Old open fallback should not be used.")
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u12open",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12open",
        build_update(text="What happens now and when will I see candidates?"),
    )

    assert templates == ["state_aware_help"]
    assert service.notifications_repo.calls[-1]["template_key"] == "state_aware_help"
    assert service.stage_agents.calls
    assert not service.bot_controller.calls


def test_graph_open_stage_can_own_delete_vacancy_intent() -> None:
    service = build_service()
    service.stage_agents = FakeStageAgentService(
        None,
        stage_result=StageAgentExecutionResult(
            stage="OPEN",
            reply_text="I can help you remove this vacancy if you want to stop matching for it.",
            stage_status="ready_for_transition",
            proposed_action="delete_vacancy",
            action_accepted=True,
            structured_payload={},
            validation_result={"accepted": True, "normalized_action": "delete_vacancy"},
        ),
    )
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.deletion_result = SimpleNamespace(
        status="confirmation_required",
        notification_template="vacancy_deletion_confirmation_required",
        notification_text="Please confirm vacancy deletion.",
    )
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u12openx",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12openx",
        build_update(text="Delete vacancy"),
    )

    assert templates == ["vacancy_deletion_confirmation_required"]
    assert service.vacancy_service.deletion_calls
    assert service.vacancy_service.deletion_calls[-1]["text"] == "delete vacancy"


def test_manager_voice_clarification_passthrough_reaches_clarification_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.vacancy_service.clarification_result = SimpleNamespace(
        status="open",
        notification_template="vacancy_open",
        notification_text="Vacancy is now open.",
    )
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u12d",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12d",
        build_update(content_type="voice"),
    )

    assert templates == ["vacancy_open"]
    assert service.vacancy_service.clarification_calls


def test_manager_reject_passthrough_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="rejected",
        notification_template="manager_candidate_rejected",
        notification_text="Candidate rejected.",
    )

    user = SimpleNamespace(
        id="u12b",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12b",
        build_update(text="Reject candidate"),
    )

    assert templates == ["manager_candidate_rejected"]
    assert service.evaluation_service.calls


def test_manager_reject_alias_passthrough_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="rejected",
        notification_template="manager_candidate_rejected",
        notification_text="Candidate rejected.",
    )

    user = SimpleNamespace(
        id="u12e",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12e",
        build_update(text="Reject"),
    )

    assert templates == ["manager_candidate_rejected"]
    assert service.evaluation_service.calls


def test_manager_reject_with_punctuation_reaches_manager_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FailIfCalledService()
    service.interview_service = FailIfCalledService()
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = SimpleNamespace(
        status="rejected",
        notification_template="manager_candidate_rejected",
        notification_text="Candidate rejected.",
    )

    user = SimpleNamespace(
        id="u12e2",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=True,
    )

    templates = service._apply_identity_flow(
        user,
        "raw12e2",
        build_update(text="Reject."),
    )

    assert templates == ["manager_candidate_rejected"]
    assert service.evaluation_service.calls


def test_unsupported_input_uses_recovery_for_user_without_active_role_flow() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u13",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw13",
        build_update(text="random unsupported thing"),
    )

    assert templates == ["unsupported_input"]
    assert service.notifications_repo.calls[-1]["template_key"] == "unsupported_input"
    assert service.notifications_repo.calls[-1]["payload_json"]["text"].startswith("Recovery:")


def test_unsupported_voice_input_uses_recovery_for_user_without_active_role_flow() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u14",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw14",
        build_update(content_type="voice"),
    )

    assert templates == ["unsupported_input"]
    assert service.notifications_repo.calls[-1]["template_key"] == "unsupported_input"
    assert service.notifications_repo.calls[-1]["payload_json"]["text"] == "Recovery: voice"


def test_unsupported_document_input_uses_recovery_for_user_without_active_role_flow() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(None)
    service.candidate_service = FakeCandidateService()
    service.interview_service = FakeInterviewService()
    service.interview_service.result = None
    service.vacancy_service = FakeVacancyService()
    service.evaluation_service = FakeEvaluationService()
    service.evaluation_service.result = None

    user = SimpleNamespace(
        id="u15",
        phone_number="+123",
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw15",
        build_update(content_type="document"),
    )

    assert templates == ["unsupported_input"]
    assert service.notifications_repo.calls[-1]["template_key"] == "unsupported_input"
    assert service.notifications_repo.calls[-1]["payload_json"]["text"] == "Recovery: document"
