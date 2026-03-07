from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.interview.service import InterviewService


class FakeSession:
    pass


class FakeCandidateRepository:
    def __init__(self, candidate, candidate_version):
        self.candidate = candidate
        self.candidate_version = candidate_version

    def get_active_by_user_id(self, user_id):
        return self.candidate if self.candidate.user_id == user_id else None

    def get_by_id(self, profile_id):
        return self.candidate if self.candidate.id == profile_id else None

    def get_version_by_id(self, version_id):
        return self.candidate_version if self.candidate_version.id == version_id else None


class FakeMatchingRepository:
    def __init__(self, match, matching_run):
        self.match = match
        self.matching_run = matching_run
        self.invite_waves = []

    def list_shortlisted_for_vacancy(self, vacancy_id, *, limit=3):
        if self.match.vacancy_id == vacancy_id and self.match.status == "shortlisted":
            return [self.match]
        return []

    def count_shortlisted_for_vacancy(self, vacancy_id):
        if self.match.vacancy_id == vacancy_id and self.match.status == "shortlisted":
            return 1
        return 0

    def mark_invited(self, match):
        match.status = "invited"
        match.invitation_sent_at = "now"
        return match

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        if self.match.candidate_profile_id == candidate_profile_id and self.match.status == "invited":
            return self.match
        return None

    def mark_candidate_responded(self, match, *, status):
        match.status = status
        match.candidate_response_at = "now"
        return match

    def get_by_id(self, match_id):
        return self.match if self.match.id == match_id else None

    def get_run_by_id(self, matching_run_id):
        return self.matching_run if self.matching_run.id == matching_run_id else None

    def get_latest_run_for_vacancy(self, vacancy_id, *, status=None):
        if self.matching_run.vacancy_id != vacancy_id:
            return None
        if status is not None and self.matching_run.status != status:
            return None
        return self.matching_run

    def get_next_wave_no(self, matching_run_id):
        if not self.invite_waves:
            return 1
        return max(wave.wave_no for wave in self.invite_waves if wave.matching_run_id == matching_run_id) + 1

    def create_invite_wave(self, **kwargs):
        wave = SimpleNamespace(id=uuid4(), **kwargs)
        self.invite_waves.append(wave)
        return wave

    def complete_invite_wave(self, wave, **kwargs):
        for key, value in kwargs.items():
            setattr(wave, key, value)
        return wave


class FakeVacancyRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_by_id(self, vacancy_id):
        return self.vacancy if self.vacancy.id == vacancy_id else None


class FakeInterviewsRepository:
    def __init__(self):
        self.session = None
        self.questions = []
        self.answers = []

    def get_session_by_match_id(self, match_id):
        if self.session and self.session.match_id == match_id:
            return self.session
        return None

    def get_active_session_for_candidate(self, candidate_profile_id):
        if self.session and self.session.candidate_profile_id == candidate_profile_id and self.session.state in {"INVITED", "ACCEPTED", "IN_PROGRESS"}:
            return self.session
        return None

    def create_session(self, **kwargs):
        self.session = SimpleNamespace(
            id=uuid4(),
            current_question_order=1,
            total_questions=0,
            invited_at=None,
            accepted_at=None,
            started_at=None,
            completed_at=None,
            **kwargs,
        )
        return self.session

    def create_question(self, **kwargs):
        question = SimpleNamespace(id=uuid4(), asked_at=None, answered_at=None, **kwargs)
        self.questions.append(question)
        return question

    def set_total_questions(self, session, total_questions):
        session.total_questions = total_questions
        return session

    def get_question_by_order(self, session_id, order_no):
        for question in self.questions:
            if question.session_id == session_id and question.order_no == order_no:
                return question
        return None

    def mark_question_asked(self, question):
        question.asked_at = "now"
        return question

    def mark_question_answered(self, question):
        question.answered_at = "now"
        return question

    def create_answer(self, **kwargs):
        answer = SimpleNamespace(id=uuid4(), **kwargs)
        self.answers.append(answer)
        return answer

    def advance_question_pointer(self, session, next_order):
        session.current_question_order = next_order
        return session

    def shift_questions_from_order(self, session_id, start_order, delta=1):
        for question in sorted(
            [item for item in self.questions if item.session_id == session_id and item.order_no >= start_order],
            key=lambda item: item.order_no,
            reverse=True,
        ):
            question.order_no += delta

    def mark_accepted(self, session):
        session.accepted_at = "now"
        return session

    def mark_started(self, session):
        session.started_at = "now"
        return session

    def mark_completed(self, session):
        session.completed_at = "now"
        return session


class FakeNotificationsRepository:
    def __init__(self):
        self.rows = []

    def create(self, **kwargs):
        self.rows.append(SimpleNamespace(**kwargs))
        return self.rows[-1]


class FakeStateService:
    def __init__(self):
        self.transitions = []

    def record_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def transition(self, **kwargs):
        entity = kwargs["entity"]
        field = kwargs.get("state_field", "state")
        setattr(entity, field, kwargs["to_state"])
        self.transitions.append(kwargs)


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


def _build_service():
    candidate = SimpleNamespace(id=uuid4(), user_id=uuid4())
    candidate_version = SimpleNamespace(id=uuid4(), summary_json={"years_experience": 6, "skills": ["python", "postgresql"]})
    vacancy = SimpleNamespace(id=uuid4(), role_title="Senior Python Engineer", primary_tech_stack_json=["python", "postgresql"])
    matching_run = SimpleNamespace(id=uuid4(), vacancy_id=vacancy.id, status="completed")
    match = SimpleNamespace(
        id=uuid4(),
        matching_run_id=matching_run.id,
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id=candidate_version.id,
        status="shortlisted",
        invitation_sent_at=None,
        candidate_response_at=None,
    )
    service = InterviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate, candidate_version)
    service.matches = FakeMatchingRepository(match, matching_run)
    service.vacancies = FakeVacancyRepository(vacancy)
    service.interviews = FakeInterviewsRepository()
    service.notifications = FakeNotificationsRepository()
    service.state_service = FakeStateService()
    service.queue = FakeQueue()
    return service, candidate, match, vacancy, matching_run


def test_dispatch_invites_for_vacancy_marks_match_invited() -> None:
    service, candidate, match, vacancy, matching_run = _build_service()

    result = service.dispatch_invites_for_vacancy(vacancy_id=vacancy.id, matching_run_id=matching_run.id)

    assert result["invited_count"] == 1
    assert result["wave_no"] == 1
    assert result["remaining_shortlisted_count"] == 0
    assert result["shortlist_exhausted"] is True
    assert match.status == "invited"
    assert service.matches.invite_waves[0].invited_count == 1
    assert service.matches.invite_waves[0].matching_run_id == matching_run.id
    assert service.notifications.rows[0].user_id == candidate.user_id


def test_dispatch_invites_for_vacancy_returns_without_wave_when_shortlist_empty() -> None:
    service, _candidate, match, vacancy, matching_run = _build_service()
    match.status = "invited"

    result = service.dispatch_invites_for_vacancy(vacancy_id=vacancy.id, matching_run_id=matching_run.id)

    assert result["invited_count"] == 0
    assert result["invite_wave_id"] is None
    assert result["wave_no"] is None
    assert result["remaining_shortlisted_count"] == 0
    assert result["shortlist_exhausted"] is True
    assert service.matches.invite_waves == []


def test_accept_invitation_starts_interview() -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)

    result = service.handle_candidate_message(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Accept interview",
    )

    assert result is not None
    assert result.status == "accepted"
    assert match.status == "accepted"
    assert service.interviews.session is not None
    assert service.interviews.session.state == "IN_PROGRESS"
    assert len(service.interviews.questions) == 4


def test_interview_answers_complete_session() -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.handle_candidate_message(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Accept interview",
    )

    for index in range(4):
        result = service.handle_candidate_message(
            user=user,
            raw_message_id=uuid4(),
            content_type="text",
            text=f"Answer {index + 1}",
        )

    assert result is not None
    assert result.status == "completed"
    assert service.interviews.session.state == "COMPLETED"
    assert match.status == "interview_completed"
    assert len(service.interviews.answers) == 4


def test_strong_answer_inserts_followup_question(monkeypatch: pytest.MonkeyPatch) -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.handle_candidate_message(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Accept interview",
    )

    monkeypatch.setattr(
        "src.interview.service.safe_parse_interview_answer",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "answer_summary": "Candidate explained a concrete ownership-heavy example.",
                "technologies": ["python"],
                "systems_or_projects": ["payments api"],
                "ownership_level": "strong",
                "is_concrete": True,
                "possible_profile_conflict": False,
            }
        ),
    )
    monkeypatch.setattr(
        "src.interview.service.safe_decide_interview_followup",
        lambda *args, **kwargs: SimpleNamespace(
            payload={
                "answer_quality": "strong",
                "ask_followup": True,
                "followup_reason": "deepen",
                "followup_question": "What trade-off did you make there?",
            }
        ),
    )

    result = service.handle_candidate_message(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="I designed and implemented the API myself.",
    )

    assert result is not None
    assert result.status == "follow_up_question"
    assert result.notification_text == "What trade-off did you make there?"
    assert service.interviews.session.current_question_order == 2
    assert service.interviews.session.total_questions == 5
    inserted = service.interviews.get_question_by_order(service.interviews.session.id, 2)
    assert inserted is not None
    assert inserted.question_kind == "follow_up"
