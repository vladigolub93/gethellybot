from types import SimpleNamespace

from src.orchestrator.service import BotControllerService


class FakeConsentsRepository:
    def __init__(self, granted: bool):
        self.granted = granted

    def has_granted(self, user_id, consent_type: str) -> bool:
        return self.granted


class FakeCandidateRepository:
    def __init__(self, candidate=None):
        self.candidate = candidate

    def get_active_by_user_id(self, user_id):
        return self.candidate


class FakeInterviewRepository:
    def __init__(self, interview=None):
        self.interview = interview

    def get_active_session_for_candidate(self, candidate_profile_id):
        return self.interview


class FakeVacanciesRepository:
    def __init__(self, vacancy=None):
        self.vacancy = vacancy

    def get_latest_incomplete_by_manager_user_id(self, user_id):
        return self.vacancy


def test_build_recovery_message_for_candidate_summary_review() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="SUMMARY_REVIEW")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.build_recovery_message(user=user, latest_user_message="what now?")

    assert "current step" in message.lower() or "approve" in message.lower()


def test_build_recovery_message_for_cv_pending_uses_state_guidance() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="CV_PENDING")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.build_recovery_message(user=user, latest_user_message="I do not have a CV")

    assert "linkedin" in message.lower() or "voice" in message.lower() or "paste" in message.lower()


def test_maybe_build_in_state_assistance_for_cv_pending_help_request() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="CV_PENDING")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="What if I do not have a CV yet?",
    )

    assert message is not None
    assert "voice" in message.lower() or "linkedin" in message.lower() or "paste" in message.lower()


def test_maybe_build_in_state_assistance_does_not_intercept_likely_cv_text() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="CV_PENDING")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message=(
            "Senior Python backend engineer with 6 years of experience building APIs, "
            "payments integrations, PostgreSQL services, and internal platform systems."
        ),
    )

    assert message is None


def test_maybe_build_in_state_assistance_for_questions_pending_help_request() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="QUESTIONS_PENDING")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="Why do you need my salary expectations?",
    )

    assert message is not None
    assert "match" in message.lower() or "salary" in message.lower()


def test_build_recovery_message_for_missing_contact() -> None:
    user = SimpleNamespace(id="u1", phone_number=None, is_candidate=False, is_hiring_manager=False)
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=False)
    service.candidates = FakeCandidateRepository()
    service.interviews = FakeInterviewRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.build_recovery_message(user=user, latest_user_message="hello")

    assert message == "Please share your contact using the button below to continue."
