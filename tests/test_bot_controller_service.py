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
    def __init__(self, vacancy=None, vacancies=None):
        self.vacancy = vacancy
        self.vacancies = vacancies or ([] if vacancy is None else [vacancy])

    def get_latest_incomplete_by_manager_user_id(self, user_id):
        return self.vacancy

    def get_by_manager_user_id(self, user_id):
        return list(self.vacancies)


class FakeMatchingRepository:
    def __init__(self, invited_match=None, manager_review_match=None):
        self.invited_match = invited_match
        self.manager_review_match = manager_review_match

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        return self.invited_match

    def get_latest_manager_review_for_manager(self, vacancy_ids, *, manager_review_only: bool = True):
        return self.manager_review_match


def test_build_recovery_message_for_candidate_summary_review() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="SUMMARY_REVIEW")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
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
    service.matching = FakeMatchingRepository()
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
    service.matching = FakeMatchingRepository()
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
    service.matching = FakeMatchingRepository()
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
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="Why do you need my salary expectations?",
    )

    assert message is not None
    assert "match" in message.lower() or "salary" in message.lower()


def test_maybe_build_in_state_assistance_for_summary_review_help_request() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="SUMMARY_REVIEW")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="What should I change here if something is wrong?",
    )

    assert message is not None
    assert "correction" in message.lower() or "incorrect" in message.lower() or "approve" in message.lower()


def test_build_recovery_message_for_missing_contact() -> None:
    user = SimpleNamespace(id="u1", phone_number=None, is_candidate=False, is_hiring_manager=False)
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=False)
    service.candidates = FakeCandidateRepository()
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.build_recovery_message(user=user, latest_user_message="hello")

    assert message == "Please share your contact using the button below to continue."


def test_maybe_build_in_state_assistance_for_verification_constraint() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="VERIFICATION_PENDING")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="I cannot record a video right now because I am on desktop.",
    )

    assert message is not None
    assert "later" in message.lower() or "device" in message.lower() or "video" in message.lower()


def test_maybe_build_in_state_assistance_for_vacancy_intake_without_jd() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=False, is_hiring_manager=True)
    vacancy = SimpleNamespace(id="v1", state="INTAKE_PENDING")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository()
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository(vacancy)

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="I do not have a formal JD. What should I send instead?",
    )

    assert message is not None
    assert "text" in message.lower() or "voice" in message.lower() or "role details" in message.lower()


def test_maybe_build_in_state_assistance_for_vacancy_clarification_question() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=False, is_hiring_manager=True)
    vacancy = SimpleNamespace(id="v1", state="CLARIFICATION_QA")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository()
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository(vacancy)

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="Can I send an approximate budget for now?",
    )

    assert message is not None
    assert "budget" in message.lower() or "approximate" in message.lower() or "range" in message.lower()


def test_maybe_build_in_state_assistance_for_candidate_ready_question() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="READY")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="What happens now? Do I need to do anything else?",
    )

    assert message is not None
    assert "match" in message.lower() or "profile is ready" in message.lower() or "strong match" in message.lower()


def test_maybe_build_in_state_assistance_for_vacancy_open_question() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=False, is_hiring_manager=True)
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository()
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository(vacancy=None)

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="What happens now and when will I see candidates?",
    )

    assert message is not None
    assert "vacancy is open" in message.lower() or "qualified" in message.lower() or "candidates" in message.lower()


def test_maybe_build_in_state_assistance_for_interview_invited_question() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="READY")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository(invited_match=SimpleNamespace(id="m1", status="invited"))
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="How long does this interview take and can I answer by voice?",
    )

    assert message is not None
    assert "interview" in message.lower() or "telegram" in message.lower() or "voice" in message.lower()


def test_maybe_build_in_state_assistance_for_interview_in_progress_question() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=True, is_hiring_manager=False)
    candidate = SimpleNamespace(id="c1", state="READY")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository(candidate)
    service.interviews = FakeInterviewRepository(interview=SimpleNamespace(state="IN_PROGRESS"))
    service.matching = FakeMatchingRepository()
    service.vacancies = FakeVacanciesRepository()

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="Can you repeat what you mean here?",
    )

    assert message is not None
    assert "current interview question" in message.lower() or "text, voice, or video" in message.lower()


def test_maybe_build_in_state_assistance_for_manager_review_question() -> None:
    user = SimpleNamespace(id="u1", phone_number="+123", is_candidate=False, is_hiring_manager=True)
    vacancy = SimpleNamespace(id="v1", state="OPEN")
    service = BotControllerService(session=object())
    service.consents = FakeConsentsRepository(granted=True)
    service.candidates = FakeCandidateRepository()
    service.interviews = FakeInterviewRepository()
    service.matching = FakeMatchingRepository(manager_review_match=SimpleNamespace(id="m1", status="manager_review"))
    service.vacancies = FakeVacanciesRepository(vacancy=None, vacancies=[vacancy])

    message = service.maybe_build_in_state_assistance(
        user=user,
        latest_user_message="What do these scores mean before I approve or reject?",
    )

    assert message is not None
    assert "approve" in message.lower() or "reject" in message.lower() or "evaluation" in message.lower()
