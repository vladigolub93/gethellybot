from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from src.graph.service import StageAgentExecutionResult
from src.shared.text import normalize_command_text
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
    def build_recovery_message(self, *, user, latest_user_message: str) -> str:
        return f"Recovery: {latest_user_message}"


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


class FakeCandidateService:
    def __init__(self):
        self.start_calls = []
        self.cv_calls = []
        self.question_calls = []
        self.summary_calls = []
        self.verification_calls = []
        self.deletion_calls = []
        self.cv_result = SimpleNamespace(
            notification_template="candidate_cv_received_processing",
            status="accepted",
        )
        self.question_result = SimpleNamespace(
            notification_template="candidate_questions_follow_up",
            notification_text="Please confirm your salary and location details.",
            status="follow_up",
        )
        self.question_answer_result = None

    def start_onboarding(self, user, trigger_ref_id):
        self.start_calls.append({"user": user, "trigger_ref_id": trigger_ref_id})

    def handle_cv_intake(self, **kwargs):
        self.cv_calls.append(kwargs)
        return self.cv_result

    def handle_questions_parsed_payload(self, **kwargs):
        self.question_calls.append(kwargs)
        return self.question_result

    def handle_questions_answer(self, **kwargs):
        self.question_calls.append(kwargs)
        return self.question_answer_result

    def handle_summary_review_action(self, **kwargs):
        self.summary_calls.append(kwargs)
        return None

    def execute_summary_review_action(self, **kwargs):
        self.summary_calls.append(kwargs)
        return None

    def handle_verification_submission(self, **kwargs):
        self.verification_calls.append(kwargs)
        return None

    def handle_deletion_message(self, **kwargs):
        self.deletion_calls.append(kwargs)
        return None


class FakeVacancyService:
    def __init__(self):
        self.start_calls = []
        self.intake_calls = []
        self.summary_calls = []
        self.clarification_calls = []
        self.deletion_calls = []
        self.intake_result = SimpleNamespace(
            notification_template="vacancy_jd_received_processing",
            status="accepted",
        )
        self.summary_result = SimpleNamespace(
            notification_template="vacancy_summary_approved",
            status="approved",
        )
        self.clarification_result = SimpleNamespace(
            notification_template="vacancy_clarification_updated",
            notification_text="Vacancy details updated.",
            status="accepted",
        )
        self.clarification_answer_result = None

    def start_onboarding(self, user, trigger_ref_id):
        self.start_calls.append({"user": user, "trigger_ref_id": trigger_ref_id})

    def handle_jd_intake(self, **kwargs):
        self.intake_calls.append(kwargs)
        return self.intake_result

    def handle_summary_review_action(self, **kwargs):
        self.summary_calls.append(kwargs)
        text = normalize_command_text(kwargs.get("text") or "")
        if text in {"approve summary", "approve", "approve vacancy summary"}:
            return self.summary_result
        if text and "summary" not in text and "role is" in (kwargs.get("text") or "").lower():
            return SimpleNamespace(
                notification_template="vacancy_summary_edit_processing",
                status="edit_processing",
            )
        return None

    def handle_clarification_parsed_payload(self, **kwargs):
        self.clarification_calls.append(kwargs)
        return self.clarification_result

    def handle_clarification_answer(self, **kwargs):
        self.clarification_calls.append(kwargs)
        return self.clarification_answer_result

    def handle_deletion_message(self, **kwargs):
        self.deletion_calls.append(kwargs)
        return None


class FakeInterviewService:
    def __init__(self):
        self.calls = []
        self.result = None

    def handle_candidate_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeEvaluationService:
    def __init__(self):
        self.calls = []
        self.result = None

    def handle_manager_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class DispatchingStageAgentService:
    def __init__(self):
        self.calls = []

    def maybe_build_entry_reply(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        result = self.maybe_run_entry_stage(
            user=user,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        if result is not None and not result.action_accepted:
            return result.reply_text
        return None

    def maybe_build_stage_reply(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        result = self.maybe_run_stage(
            user=user,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        if result is not None and not result.action_accepted:
            return result.reply_text
        return None

    def maybe_run_entry_stage(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        command = normalize_command_text(latest_user_message)
        self.calls.append({"kind": "entry", "text": latest_user_message, "command": command})

        if not (getattr(user, "phone_number", None) or getattr(user, "username", None)):
            if "why" in (latest_user_message or "").lower():
                return StageAgentExecutionResult(
                    stage="CONTACT_REQUIRED",
                    reply_text="Helly needs your contact to link your Telegram account to one profile before onboarding can continue.",
                    stage_status="in_progress",
                    proposed_action=None,
                    action_accepted=False,
                )
            return None

        if not getattr(user, "is_candidate", False) and not getattr(user, "is_hiring_manager", False):
            if command == "candidate":
                return StageAgentExecutionResult(
                    stage="ROLE_SELECTION",
                    reply_text=None,
                    stage_status="completed",
                    proposed_action="candidate",
                    action_accepted=True,
                )
            if command == "hiring manager":
                return StageAgentExecutionResult(
                    stage="ROLE_SELECTION",
                    reply_text=None,
                    stage_status="completed",
                    proposed_action="hiring_manager",
                    action_accepted=True,
                )
        return None

    def maybe_run_stage(self, *, user, latest_user_message: str, latest_message_type: str = "text"):
        command = normalize_command_text(latest_user_message)
        self.calls.append(
            {
                "kind": "stage",
                "text": latest_user_message,
                "command": command,
                "message_type": latest_message_type,
                "candidate": getattr(user, "is_candidate", False),
                "manager": getattr(user, "is_hiring_manager", False),
            }
        )

        if getattr(user, "is_candidate", False):
            if "senior backend engineer" in (latest_user_message or "").lower():
                return StageAgentExecutionResult(
                    stage="CV_PENDING",
                    reply_text="Thanks. I will use this experience input to prepare your profile summary.",
                    stage_status="ready_for_transition",
                    proposed_action="send_cv_text",
                    action_accepted=True,
                    structured_payload={"cv_text": latest_user_message},
                )
            if "3000 usd" in (latest_user_message or "").lower():
                return StageAgentExecutionResult(
                    stage="QUESTIONS_PENDING",
                    reply_text="Thanks. I will update your preferences from this answer.",
                    stage_status="ready_for_transition",
                    proposed_action="send_salary_location_work_format",
                    action_accepted=True,
                    structured_payload={
                        "salary_amount": 3000,
                        "salary_currency": "USD",
                        "salary_period": "month",
                        "location": "Warsaw",
                        "work_format": "remote",
                    },
                )
            if command == "accept interview":
                return StageAgentExecutionResult(
                    stage="INTERVIEW_INVITED",
                    reply_text="Understood. I will start the interview.",
                    stage_status="ready_for_transition",
                    proposed_action="accept_interview",
                    action_accepted=True,
                )
            if "implemented the event-driven pipeline" in (latest_user_message or "").lower():
                return StageAgentExecutionResult(
                    stage="INTERVIEW_IN_PROGRESS",
                    reply_text="Thanks. I will use this as your current interview answer.",
                    stage_status="ready_for_transition",
                    proposed_action="answer_current_question",
                    action_accepted=True,
                    structured_payload={"answer_text": latest_user_message},
                )

        if getattr(user, "is_hiring_manager", False):
            if "senior python engineer" in (latest_user_message or "").lower():
                return StageAgentExecutionResult(
                    stage="INTAKE_PENDING",
                    reply_text="Thanks. I will use this text as the vacancy description.",
                    stage_status="ready_for_transition",
                    proposed_action="send_job_description_text",
                    action_accepted=True,
                    structured_payload={"job_description_text": latest_user_message},
                )
            if command == "approve summary":
                return StageAgentExecutionResult(
                    stage="VACANCY_SUMMARY_REVIEW",
                    reply_text="Understood. I will lock the summary and move to the required vacancy details.",
                    stage_status="ready_for_transition",
                    proposed_action="approve_summary",
                    action_accepted=True,
                )
            if "budget: 7000-9000 usd" in (latest_user_message or "").lower():
                return StageAgentExecutionResult(
                    stage="CLARIFICATION_QA",
                    reply_text="Thanks. I will update the vacancy from this clarification.",
                    stage_status="ready_for_transition",
                    proposed_action="send_vacancy_clarifications",
                    action_accepted=True,
                    structured_payload={
                        "budget_min": 7000,
                        "budget_max": 9000,
                        "work_format": "remote",
                        "countries_allowed": ["Poland", "Germany"],
                    },
                )
            if command == "approve candidate":
                return StageAgentExecutionResult(
                    stage="MANAGER_REVIEW",
                    reply_text="Understood. I will approve the candidate.",
                    stage_status="ready_for_transition",
                    proposed_action="approve_candidate",
                    action_accepted=True,
                )
        return None


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
    service.bot_controller = FakeBotController()
    service.identity_service = FakeIdentityService(consent=False)
    service.stage_agents = DispatchingStageAgentService()
    service.candidate_service = FakeCandidateService()
    service.vacancy_service = FakeVacancyService()
    service.interview_service = FakeInterviewService()
    service.evaluation_service = FakeEvaluationService()
    return service


def test_graph_owned_candidate_text_flow_routes_entry_cv_and_questions() -> None:
    service = build_service()
    user = SimpleNamespace(
        id="candidate-flow",
        phone_number=None,
        username=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(user, "raw1", build_update(text="Why do you need my contact?"))
    assert templates == ["request_contact"]

    templates = service._apply_identity_flow(
        user,
        "raw2",
        build_update(contact_phone_number="+123456789"),
    )
    assert templates == ["request_role"]
    assert user.phone_number == "+123456789"

    templates = service._apply_identity_flow(user, "raw4", build_update(text="Candidate"))
    assert templates == ["candidate_onboarding_started"]
    assert user.is_candidate is True
    assert service.candidate_service.start_calls

    templates = service._apply_identity_flow(
        user,
        "raw5",
        build_update(text="Senior backend engineer with 7 years in Python, Go, AWS, and PostgreSQL."),
    )
    assert templates == ["candidate_cv_received_processing"]
    assert service.candidate_service.cv_calls
    assert "Senior backend engineer" in service.candidate_service.cv_calls[-1]["text"]

    templates = service._apply_identity_flow(
        user,
        "raw6",
        build_update(text="3000 USD net per month, Warsaw, remote."),
    )
    assert templates == ["candidate_questions_follow_up"]
    assert service.candidate_service.question_calls
    assert service.candidate_service.question_calls[-1]["parsed_payload"]["work_format"] == "remote"


def test_graph_owned_manager_text_flow_routes_entry_intake_and_clarifications() -> None:
    service = build_service()
    user = SimpleNamespace(
        id="manager-flow",
        phone_number=None,
        username=None,
        is_candidate=False,
        is_hiring_manager=False,
    )

    templates = service._apply_identity_flow(
        user,
        "raw1",
        build_update(contact_phone_number="+123456789"),
    )
    assert templates == ["request_role"]

    templates = service._apply_identity_flow(user, "raw3", build_update(text="Hiring Manager"))
    assert templates == ["manager_onboarding_started"]
    assert user.is_hiring_manager is True
    assert service.vacancy_service.start_calls

    templates = service._apply_identity_flow(
        user,
        "raw4",
        build_update(
            text="Senior Python engineer for a fintech product. Remote in Europe. Budget up to 7000 EUR. Team of 6."
        ),
    )
    assert templates == ["vacancy_jd_received_processing"]
    assert service.vacancy_service.intake_calls
    assert "Senior Python engineer" in service.vacancy_service.intake_calls[-1]["text"]

    templates = service._apply_identity_flow(user, "raw4b", build_update(text="Approve summary"))
    assert templates == ["vacancy_summary_approved"]
    assert service.vacancy_service.summary_calls

    templates = service._apply_identity_flow(
        user,
        "raw5",
        build_update(
            text=(
                "Budget: 7000-9000 USD per month. Countries: Poland and Germany. Remote. "
                "Team size: 6. Project: B2B payments platform. Primary stack: Python, FastAPI, PostgreSQL."
            )
        ),
    )
    assert templates == ["vacancy_clarification_updated"]
    assert service.vacancy_service.clarification_calls
    assert service.vacancy_service.clarification_calls[-1]["parsed_payload"]["budget_min"] == 7000


def test_graph_owned_interaction_flow_routes_accept_answer_and_manager_approve() -> None:
    service = build_service()
    service.interview_service.result = SimpleNamespace(
        notification_template="candidate_interview_advanced",
        notification_text="Interview step accepted.",
        status="accepted",
    )
    service.evaluation_service.result = SimpleNamespace(
        notification_template="manager_candidate_review_progressed",
        notification_text="Manager review step accepted.",
        status="accepted",
    )

    candidate_user = SimpleNamespace(
        id="candidate-int",
        phone_number="+123456789",
        is_candidate=True,
        is_hiring_manager=False,
    )
    templates = service._apply_identity_flow(candidate_user, "raw1", build_update(text="Accept interview"))
    assert templates == ["candidate_interview_advanced"]
    assert service.interview_service.calls[-1]["text"] == "Accept interview"

    templates = service._apply_identity_flow(
        candidate_user,
        "raw2",
        build_update(text="I implemented the event-driven pipeline and owned the API integration."),
    )
    assert templates == ["candidate_interview_advanced"]
    assert "event-driven pipeline" in service.interview_service.calls[-1]["text"]

    manager_user = SimpleNamespace(
        id="manager-int",
        phone_number="+123456789",
        is_candidate=False,
        is_hiring_manager=True,
    )
    templates = service._apply_identity_flow(manager_user, "raw3", build_update(text="Approve candidate"))
    assert templates == ["manager_candidate_review_progressed"]
    assert service.evaluation_service.calls[-1]["text"] == "Approve candidate"
