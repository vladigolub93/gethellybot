from types import SimpleNamespace
from uuid import uuid4

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
    def __init__(self, match):
        self.match = match

    def list_shortlisted_for_vacancy(self, vacancy_id, *, limit=3):
        if self.match.vacancy_id == vacancy_id and self.match.status == "shortlisted":
            return [self.match]
        return []

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
    match = SimpleNamespace(
        id=uuid4(),
        vacancy_id=vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id=candidate_version.id,
        status="shortlisted",
        invitation_sent_at=None,
        candidate_response_at=None,
    )
    service = InterviewService(FakeSession())
    service.candidates = FakeCandidateRepository(candidate, candidate_version)
    service.matches = FakeMatchingRepository(match)
    service.vacancies = FakeVacancyRepository(vacancy)
    service.interviews = FakeInterviewsRepository()
    service.notifications = FakeNotificationsRepository()
    service.state_service = FakeStateService()
    service.queue = FakeQueue()
    return service, candidate, match, vacancy


def test_dispatch_invites_for_vacancy_marks_match_invited() -> None:
    service, candidate, match, vacancy = _build_service()

    result = service.dispatch_invites_for_vacancy(vacancy_id=vacancy.id)

    assert result["invited_count"] == 1
    assert match.status == "invited"
    assert service.notifications.rows[0].user_id == candidate.user_id


def test_accept_invitation_starts_interview() -> None:
    service, candidate, match, _vacancy = _build_service()
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
    assert len(service.interviews.questions) == 5


def test_interview_answers_complete_session() -> None:
    service, candidate, match, _vacancy = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.handle_candidate_message(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Accept interview",
    )

    for index in range(5):
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
    assert len(service.interviews.answers) == 5
