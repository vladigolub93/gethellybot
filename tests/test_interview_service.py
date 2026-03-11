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


class FakeUsersRepository:
    def __init__(self, users):
        self.users = users

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class FakeMatchingRepository:
    def __init__(self, match, matching_run, extra_matches=None):
        self.match = match
        self.matches = [match] + list(extra_matches or [])
        self.matching_run = matching_run
        self.invite_waves = []

    def list_shortlisted_for_vacancy(self, vacancy_id, *, limit=3):
        rows = [
            match
            for match in self.matches
            if match.vacancy_id == vacancy_id and match.status == "shortlisted"
        ]
        return rows[:limit]

    def count_shortlisted_for_vacancy(self, vacancy_id):
        return len(
            [
                match
                for match in self.matches
                if match.vacancy_id == vacancy_id and match.status == "shortlisted"
            ]
        )

    def mark_invited(self, match):
        match.status = "invited"
        match.invitation_sent_at = "now"
        return match

    def get_latest_invited_for_candidate(self, candidate_profile_id):
        for match in reversed(self.matches):
            if match.candidate_profile_id == candidate_profile_id and match.status == "invited":
                return match
        return None

    def get_next_queued_for_candidate(self, candidate_profile_id):
        for match in self.matches:
            if match.candidate_profile_id == candidate_profile_id and match.status == "interview_queued":
                return match
        return None

    def mark_candidate_responded(self, match, *, status):
        match.status = status
        match.candidate_response_at = "now"
        return match

    def get_by_id(self, match_id):
        for match in self.matches:
            if str(match.id) == str(match_id):
                return match
        return None

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
        self.sessions = {}
        self.questions = []
        self.answers = []

    def get_session_by_match_id(self, match_id):
        if match_id in self.sessions:
            return self.sessions[match_id]
        if self.session and self.session.match_id == match_id:
            return self.session
        return None

    def get_active_session_for_candidate(self, candidate_profile_id):
        for session in reversed(list(self.sessions.values())):
            if session.candidate_profile_id == candidate_profile_id and session.state in {"INVITED", "ACCEPTED", "IN_PROGRESS"}:
                return session
        if self.session and self.session.candidate_profile_id == candidate_profile_id and self.session.state in {"INVITED", "ACCEPTED", "IN_PROGRESS"}:
            return self.session
        return None

    def create_session(self, **kwargs):
        created = SimpleNamespace(
            id=uuid4(),
            current_question_order=1,
            total_questions=0,
            invited_at=None,
            accepted_at=None,
            started_at=None,
            completed_at=None,
            **kwargs,
        )
        self.session = created
        self.sessions[created.match_id] = created
        return created

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


class FakeReviewService:
    def __init__(self, *, result=None):
        self.calls = []
        self.result = result or {"status": "dispatched", "batch_count": 1, "notified": True}

    def dispatch_manager_batch_for_vacancy(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.result)


def _build_service():
    candidate = SimpleNamespace(id=uuid4(), user_id=uuid4())
    candidate_version = SimpleNamespace(id=uuid4(), summary_json={"years_experience": 6, "skills": ["python", "postgresql"]})
    vacancy = SimpleNamespace(id=uuid4(), role_title="Senior Python Engineer", primary_tech_stack_json=["python", "postgresql"], manager_user_id=None)
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
    service.users = FakeUsersRepository(
        {candidate.user_id: SimpleNamespace(id=candidate.user_id, display_name="Test Candidate")}
    )
    service.review_service = FakeReviewService()
    service.state_service = FakeStateService()
    service.queue = FakeQueue()
    return service, candidate, match, vacancy, matching_run


def test_dispatch_invites_for_vacancy_routes_legacy_job_to_manager_review() -> None:
    service, _candidate, match, vacancy, matching_run = _build_service()

    result = service.dispatch_invites_for_vacancy(vacancy_id=vacancy.id, matching_run_id=matching_run.id)

    assert result["invited_count"] == 0
    assert result["invite_wave_id"] is None
    assert result["wave_no"] is None
    assert result["remaining_shortlisted_count"] == 1
    assert result["shortlist_exhausted"] is False
    assert result["routed_to_manager_review"] is True
    assert result["manager_review_status"] == "dispatched"
    assert match.status == "shortlisted"
    assert service.matches.invite_waves == []
    assert service.review_service.calls == [
        {"vacancy_id": vacancy.id, "force": True, "trigger_type": "job"}
    ]
    assert service.notifications.rows == []


def test_dispatch_invites_for_vacancy_returns_without_wave_when_shortlist_empty() -> None:
    service, _candidate, match, vacancy, matching_run = _build_service()
    match.status = "invited"

    result = service.dispatch_invites_for_vacancy(vacancy_id=vacancy.id, matching_run_id=matching_run.id)

    assert result["invited_count"] == 0
    assert result["invite_wave_id"] is None
    assert result["wave_no"] is None
    assert result["remaining_shortlisted_count"] == 0
    assert result["shortlist_exhausted"] is True
    assert result["routed_to_manager_review"] is False
    assert service.matches.invite_waves == []


def test_accept_invitation_starts_interview() -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)

    result = service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    assert result is not None
    assert result.status == "accepted"
    assert match.status == "accepted"
    assert service.interviews.session is not None
    assert service.interviews.session.state == "IN_PROGRESS"
    assert len(service.interviews.questions) == 4


def test_accept_invitation_starts_interview_when_match_id_is_provided() -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)

    result = service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
        match_id=str(match.id),
    )

    assert result is not None
    assert result.status == "accepted"
    assert match.status == "accepted"
    assert service.interviews.session is not None
    assert service.interviews.session.match_id == match.id


def test_accept_invitation_notifies_manager() -> None:
    service, candidate, match, vacancy, _matching_run = _build_service()
    vacancy.manager_user_id = uuid4()
    service.users.users[vacancy.manager_user_id] = SimpleNamespace(
        id=vacancy.manager_user_id,
        display_name="Hiring Manager",
    )
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)

    result = service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    assert result is not None
    assert result.status == "accepted"
    assert service.notifications.rows[-1].user_id == vacancy.manager_user_id
    assert "accepted the interview invitation" in service.notifications.rows[-1].payload_json["text"].lower()


def test_accept_invitation_builds_questions_from_persisted_cv_text(monkeypatch: pytest.MonkeyPatch) -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    service.candidates.candidate_version.extracted_text = "Senior backend engineer with 7 years using Python, PostgreSQL, and AWS on fintech APIs."
    user = SimpleNamespace(id=candidate.user_id)
    captured = {}

    def _fake_build_plan(_session, vacancy, candidate_summary, cv_text=None):
        captured["vacancy"] = vacancy
        captured["candidate_summary"] = candidate_summary
        captured["cv_text"] = cv_text
        return SimpleNamespace(
            payload={
                "questions": [
                    {"id": 1, "type": "behavioral", "question": "Q1"},
                    {"id": 2, "type": "situational", "question": "Q2"},
                    {"id": 3, "type": "role_specific", "question": "Q3"},
                    {"id": 4, "type": "motivation", "question": "Q4"},
                ]
            }
        )

    monkeypatch.setattr("src.interview.service.safe_build_interview_question_plan", _fake_build_plan)

    result = service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    assert result is not None
    assert result.status == "accepted"
    assert captured["cv_text"] == "Senior backend engineer with 7 years using Python, PostgreSQL, and AWS on fintech APIs."


def test_skip_opportunity_notifies_manager_and_marks_declined() -> None:
    service, candidate, match, vacancy, _matching_run = _build_service()
    vacancy.manager_user_id = uuid4()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)

    result = service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="skip_opportunity",
    )

    assert result is not None
    assert result.status == "skipped"
    assert match.status == "candidate_declined_interview"
    assert service.notifications.rows[-1].user_id == vacancy.manager_user_id
    assert "declined the interview invitation" in service.notifications.rows[-1].payload_json["text"].lower()


def test_accept_invitation_queues_when_another_interview_is_active() -> None:
    service, candidate, match, vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    active_match = SimpleNamespace(
        id=uuid4(),
        vacancy_id=uuid4(),
        candidate_profile_id=candidate.id,
        candidate_profile_version_id=service.candidates.candidate_version.id,
        status="accepted",
        candidate_response_at="earlier",
    )
    active_session = SimpleNamespace(
        id=uuid4(),
        match_id=active_match.id,
        candidate_profile_id=candidate.id,
        vacancy_id=active_match.vacancy_id,
        state="IN_PROGRESS",
        current_question_order=1,
        total_questions=1,
    )
    service.matches.matches.append(active_match)
    service.interviews.sessions[active_match.id] = active_session
    service.interviews.session = active_session
    vacancy.manager_user_id = uuid4()
    user = SimpleNamespace(id=candidate.user_id)

    result = service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    assert result is not None
    assert result.status == "queued"
    assert match.status == "interview_queued"
    queued_session = service.interviews.get_session_by_match_id(match.id)
    assert queued_session is not None
    assert queued_session.state == "CREATED"
    assert service.notifications.rows[-1].user_id == vacancy.manager_user_id
    assert "queued until the current one finishes" in service.notifications.rows[-1].payload_json["text"].lower()


def test_interview_answers_complete_session() -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    for index in range(4):
        result = service.execute_active_interview_action(
            user=user,
            raw_message_id=uuid4(),
            action="answer_current_question",
            content_type="text",
            text=f"Answer {index + 1}",
        )

    assert result is not None
    assert result.status == "completed"
    assert service.interviews.session.state == "COMPLETED"
    assert match.status == "interview_completed"
    assert len(service.interviews.answers) == 4


def test_completing_interview_starts_next_queued_interview() -> None:
    service, candidate, match, vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    queued_vacancy = SimpleNamespace(
        id=uuid4(),
        role_title="Queued Platform Role",
        primary_tech_stack_json=["python"],
        manager_user_id=uuid4(),
    )
    queued_match = SimpleNamespace(
        id=uuid4(),
        matching_run_id=uuid4(),
        vacancy_id=queued_vacancy.id,
        candidate_profile_id=candidate.id,
        candidate_profile_version_id=service.candidates.candidate_version.id,
        status="invited",
        invitation_sent_at="now",
        candidate_response_at=None,
    )
    service.matches.matches.append(queued_match)
    service.vacancies.vacancy = vacancy
    original_get_by_id = service.vacancies.get_by_id
    service.vacancies.get_by_id = lambda vacancy_id: queued_vacancy if vacancy_id == queued_vacancy.id else original_get_by_id(vacancy_id)
    service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    for index in range(4):
        result = service.execute_active_interview_action(
            user=user,
            raw_message_id=uuid4(),
            action="answer_current_question",
            content_type="text",
            text=f"Answer {index + 1}",
        )

    assert result is not None
    assert result.status == "completed"
    queued_session = service.interviews.get_session_by_match_id(queued_match.id)
    assert queued_session is not None
    assert queued_match.status == "accepted"
    assert queued_session.state == "IN_PROGRESS"
    assert service.notifications.rows[-1].user_id == candidate.user_id
    assert "next queued interview is starting now" in service.notifications.rows[-1].payload_json["messages"][0].lower()


def test_cancel_active_interview_marks_declined() -> None:
    service, candidate, match, vacancy, _matching_run = _build_service()
    vacancy.manager_user_id = uuid4()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    result = service.execute_active_interview_action(
        user=user,
        raw_message_id=uuid4(),
        action="cancel_interview",
        content_type="text",
        text="Cancel interview",
    )

    assert result is not None
    assert result.status == "cancelled"
    assert match.status == "candidate_declined_interview"
    assert service.interviews.session.state == "CANCELLED"
    assert service.notifications.rows[-1].user_id == vacancy.manager_user_id
    assert "cancelled the interview" in service.notifications.rows[-1].payload_json["text"].lower()


def test_execute_active_interview_action_answers_current_question() -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
    )

    result = service.execute_active_interview_action(
        user=user,
        raw_message_id=uuid4(),
        action="answer_current_question",
        content_type="text",
        text="I owned the API design and rollout.",
    )

    assert result is not None
    assert result.status in {"next_question", "follow_up_question", "completed"}
    assert len(service.interviews.answers) == 1


def test_strong_answer_inserts_followup_question(monkeypatch: pytest.MonkeyPatch) -> None:
    service, candidate, match, _vacancy, _matching_run = _build_service()
    service.matches.mark_invited(match)
    user = SimpleNamespace(id=candidate.user_id)
    service.execute_invitation_action(
        user=user,
        raw_message_id=uuid4(),
        action="accept_interview",
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

    result = service.execute_active_interview_action(
        user=user,
        raw_message_id=uuid4(),
        action="answer_current_question",
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
