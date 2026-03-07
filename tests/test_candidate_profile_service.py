from types import SimpleNamespace
from uuid import uuid4

from src.candidate_profile.service import CandidateProfileService
from src.candidate_profile.states import (
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_SUMMARY_REVIEW,
    CANDIDATE_STATE_VERIFICATION_PENDING,
)


class FakeSession:
    def add(self, _obj):
        return None

    def flush(self):
        return None


class FakeCandidateProfilesRepository:
    def __init__(self):
        self.profile = None
        self.versions = []

    def get_active_by_user_id(self, _user_id):
        return self.profile

    def create(self, *, user_id, state):
        self.profile = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            state=state,
            current_version_id=None,
            questions_context_json={},
        )
        return self.profile

    def set_state(self, profile, state):
        profile.state = state
        return profile

    def next_version_no(self, _profile_id):
        return len(self.versions) + 1

    def create_version(self, **kwargs):
        version = SimpleNamespace(id=uuid4(), **kwargs)
        self.versions.append(version)
        return version

    def set_current_version(self, profile, version_id):
        profile.current_version_id = version_id
        return profile

    def update_questions_context(self, profile, questions_context_json):
        profile.questions_context_json = questions_context_json
        return profile

    def update_question_answers(self, profile, **kwargs):
        for key, value in kwargs.items():
            setattr(profile, key, value)
        return profile

    def get_current_version(self, profile):
        for version in self.versions:
            if version.id == profile.current_version_id:
                return version
        return None

    def mark_version_approved(self, version):
        version.approval_status = "approved"
        version.approved_by_user = True
        return version

    def count_versions_by_source_type(self, _profile_id, source_type):
        return len([version for version in self.versions if version.source_type == source_type])


class FakeStateService:
    def __init__(self):
        self.transitions = []

    def record_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def transition(self, **kwargs):
        entity = kwargs["entity"]
        entity.state = kwargs["to_state"]
        self.transitions.append(kwargs)


class FakeQueue:
    def __init__(self):
        self.messages = []

    def enqueue(self, message):
        self.messages.append(message)


def test_start_onboarding_moves_candidate_to_cv_pending() -> None:
    service = CandidateProfileService(FakeSession())
    service.repo = FakeCandidateProfilesRepository()
    service.state_service = FakeStateService()
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = service.start_onboarding(user, trigger_ref_id=uuid4())

    assert profile.state == CANDIDATE_STATE_CV_PENDING


def test_handle_cv_intake_transitions_to_processing() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_CV_PENDING)

    result = service.handle_cv_intake(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Python backend engineer with 5 years experience",
    )

    assert result.status == "accepted"
    assert profile.state == CANDIDATE_STATE_CV_PROCESSING
    assert len(fake_repo.versions) == 1
    assert len(fake_queue.messages) == 1


def test_approve_summary_moves_candidate_to_questions_pending() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    fake_repo.set_current_version(profile, version.id)

    result = service.handle_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        text="Approve summary",
    )

    assert result is not None
    assert result.status == "approved"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert version.approval_status == "approved"


def test_edit_summary_enqueues_processing_job() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_SUMMARY_REVIEW)
    version = fake_repo.create_version(
        profile_id=profile.id,
        version_no=1,
        source_type="pasted_text",
        summary_json={"headline": "Python engineer"},
    )
    fake_repo.set_current_version(profile, version.id)

    result = service.handle_summary_review_action(
        user=user,
        raw_message_id=uuid4(),
        text="Edit summary: emphasize backend leadership",
    )

    assert result is not None
    assert result.status == "accepted"
    assert profile.state == CANDIDATE_STATE_CV_PROCESSING
    assert len(fake_repo.versions) == 2
    assert fake_repo.versions[-1].source_type == "summary_user_edit"
    assert len(fake_queue.messages) == 1


def test_questions_answer_completion_moves_profile_to_verification_pending() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="Salary: $5000 per month. Location: Warsaw, Poland. Remote.",
    )

    assert result is not None
    assert result.status == "completed"
    assert profile.state == CANDIDATE_STATE_VERIFICATION_PENDING
    assert profile.salary_min == 5000
    assert profile.work_format == "remote"


def test_questions_answer_requests_follow_up_when_partial() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = FakeQueue()

    user = SimpleNamespace(id=uuid4())
    profile = fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="text",
        text="I'm in Warsaw, Poland.",
    )

    assert result is not None
    assert result.status == "follow_up"
    assert profile.state == CANDIDATE_STATE_QUESTIONS_PENDING
    assert profile.location_text is not None


def test_questions_voice_answer_enqueues_processing_job() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    fake_queue = FakeQueue()
    service.repo = fake_repo
    service.state_service = fake_state
    service.queue = fake_queue

    user = SimpleNamespace(id=uuid4())
    fake_repo.create(user_id=user.id, state=CANDIDATE_STATE_QUESTIONS_PENDING)

    result = service.handle_questions_answer(
        user=user,
        raw_message_id=uuid4(),
        content_type="voice",
        file_id=uuid4(),
    )

    assert result is not None
    assert result.status == "queued"
    assert len(fake_queue.messages) == 1
