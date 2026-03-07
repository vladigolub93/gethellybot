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
        self.question_calls = []
        self.summary_calls = []
        self.deletion_calls = []
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

    def handle_summary_review_action(self, **kwargs):
        self.summary_calls.append(kwargs)
        return self.summary_result

    def handle_questions_answer(self, **kwargs):
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
        self.deletion_result = None
        self.clarification_result = None

    def handle_deletion_message(self, **kwargs):
        self.deletion_calls.append(kwargs)
        return self.deletion_result

    def handle_clarification_answer(self, **kwargs):
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


def build_update(*, text: Optional[str] = None, content_type: str = "text") -> NormalizedTelegramUpdate:
    return NormalizedTelegramUpdate(
        update_id=1,
        telegram_user_id=100,
        telegram_chat_id=200,
        message_id=300,
        content_type=content_type,
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


def test_candidate_questions_help_is_intercepted_before_questions_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "I need salary, location, and work format so Helly can apply matching filters correctly."
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


def test_summary_review_help_is_intercepted_before_summary_handler() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "Tell me exactly what is wrong in the summary, and I will revise it once."
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
    assert not service.candidate_service.summary_calls


def test_summary_review_actual_correction_reaches_summary_handler() -> None:
    service = build_service()
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


def test_candidate_ready_help_is_intercepted_before_fallback() -> None:
    service = build_service()
    service.bot_controller = FakeBotController(
        "Your profile is ready. Helly will contact you when a strong match is found."
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
