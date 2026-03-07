from typing import Optional

from types import SimpleNamespace

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


class FailIfCalledService:
    def __getattr__(self, item):
        def _fail(*args, **kwargs):
            raise AssertionError(f"{item} should not be called in this routing path")

        return _fail


class FakeCandidateService:
    def __init__(self):
        self.cv_calls = []
        self.verification_calls = []

    def handle_deletion_message(self, **kwargs):
        return None

    def handle_summary_review_action(self, **kwargs):
        return None

    def handle_questions_answer(self, **kwargs):
        return None

    def handle_cv_intake(self, **kwargs):
        self.cv_calls.append(kwargs)
        return SimpleNamespace(
            notification_template="candidate_cv_received_processing",
            status="accepted",
        )

    def handle_verification_submission(self, **kwargs):
        self.verification_calls.append(kwargs)
        return SimpleNamespace(
            notification_template="candidate_verification_instructions",
            notification_text="Please send the verification video.",
            status="instruction",
        )


class FakeVacancyService:
    def __init__(self):
        self.intake_calls = []

    def handle_deletion_message(self, **kwargs):
        return None

    def handle_clarification_answer(self, **kwargs):
        return None

    def handle_jd_intake(self, **kwargs):
        self.intake_calls.append(kwargs)
        return SimpleNamespace(
            notification_template="vacancy_jd_received_processing",
            status="accepted",
        )


def build_update(*, text: str) -> NormalizedTelegramUpdate:
    return NormalizedTelegramUpdate(
        update_id=1,
        telegram_user_id=100,
        telegram_chat_id=200,
        message_id=300,
        content_type="text",
        text=text,
        contact_phone_number=None,
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
    return service


def test_candidate_cv_help_is_intercepted_before_cv_intake() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "No problem. You can paste your experience as text, send a voice note, or upload a LinkedIn PDF."
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
    assert not service.candidate_service.cv_calls


def test_manager_jd_help_is_intercepted_before_jd_intake() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "Yes. You can paste the role title, stack, seniority, budget, and work format as plain text."
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
    assert not service.vacancy_service.intake_calls


def test_candidate_verification_help_is_intercepted_before_submission_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "You can do the verification later from a device with a camera. The step cannot be skipped."
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
    assert not service.candidate_service.verification_calls
