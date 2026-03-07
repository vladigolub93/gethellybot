from types import SimpleNamespace
from uuid import uuid4

from src.candidate_profile.service import CandidateProfileService
from src.candidate_profile.states import (
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
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


class FakeStateService:
    def __init__(self):
        self.transitions = []

    def record_transition(self, **kwargs):
        self.transitions.append(kwargs)

    def transition(self, **kwargs):
        entity = kwargs["entity"]
        entity.state = kwargs["to_state"]
        self.transitions.append(kwargs)


def test_start_onboarding_moves_candidate_to_cv_pending() -> None:
    service = CandidateProfileService(FakeSession())
    service.repo = FakeCandidateProfilesRepository()
    service.state_service = FakeStateService()

    user = SimpleNamespace(id=uuid4())
    profile = service.start_onboarding(user, trigger_ref_id=uuid4())

    assert profile.state == CANDIDATE_STATE_CV_PENDING


def test_handle_cv_intake_transitions_to_processing() -> None:
    service = CandidateProfileService(FakeSession())
    fake_repo = FakeCandidateProfilesRepository()
    fake_state = FakeStateService()
    service.repo = fake_repo
    service.state_service = fake_state

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
