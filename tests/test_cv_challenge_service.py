from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from src.cv_challenge.service import CandidateCvChallengeService


class FakeProfilesRepository:
    def __init__(self, profile=None, version=None):
        self.profile = profile
        self.version = version

    def get_active_by_user_id(self, user_id):
        return self.profile

    def get_current_version(self, profile):
        return self.version


class FakeMatchingRepository:
    def __init__(self, active_matches=None):
        self.active_matches = list(active_matches or [])

    def list_active_for_candidate(self, candidate_profile_id):
        return list(self.active_matches)


class FakeAttemptsRepository:
    def __init__(self):
        self.rows = {}

    def create(self, **kwargs):
        attempt = SimpleNamespace(
            id=uuid4(),
            candidate_profile_id=kwargs["candidate_profile_id"],
            candidate_profile_version_id=kwargs.get("candidate_profile_version_id"),
            status="started",
            score=0,
            lives_left=3,
            stage_reached=1,
            won=False,
            started_at=SimpleNamespace(isoformat=lambda: "2026-03-11T10:00:00+00:00"),
            finished_at=None,
            skills_snapshot_json=kwargs.get("skills_snapshot_json") or {},
            result_json=kwargs.get("result_json"),
        )
        self.rows[str(attempt.id)] = attempt
        return attempt

    def get_by_id(self, attempt_id):
        return self.rows.get(str(attempt_id))

    def get_latest_active_for_candidate_profile(self, candidate_profile_id):
        attempts = [
            row
            for row in self.rows.values()
            if str(row.candidate_profile_id) == str(candidate_profile_id) and row.finished_at is None
        ]
        return attempts[-1] if attempts else None

    def get_latest_completed_for_candidate_profile(self, candidate_profile_id):
        attempts = [
            row
            for row in self.rows.values()
            if str(row.candidate_profile_id) == str(candidate_profile_id) and row.finished_at is not None
        ]
        return attempts[-1] if attempts else None

    def save_progress(self, attempt, **kwargs):
        attempt.score = kwargs["score"]
        attempt.lives_left = kwargs["lives_left"]
        attempt.stage_reached = kwargs["stage_reached"]
        attempt.result_json = kwargs.get("progress_json")
        return attempt

    def mark_finished(self, attempt, **kwargs):
        attempt.status = "completed"
        attempt.score = kwargs["score"]
        attempt.lives_left = kwargs["lives_left"]
        attempt.stage_reached = kwargs["stage_reached"]
        attempt.won = kwargs["won"]
        attempt.finished_at = SimpleNamespace(isoformat=lambda: "2026-03-11T10:10:00+00:00")
        attempt.result_json = kwargs.get("result_json")
        return attempt


def _build_service(*, active_matches=None, skills=None):
    profile_id = uuid4()
    version_id = uuid4()
    profile = SimpleNamespace(
        id=profile_id,
        user_id=uuid4(),
        state="READY",
        current_version_id=version_id,
    )
    version = SimpleNamespace(
        id=version_id,
        summary_json={"skills": list(skills or ["react", "typescript", "docker"])},
    )
    service = CandidateCvChallengeService(session=object())
    service.settings = SimpleNamespace(app_base_url="https://helly.test")
    service.profiles = FakeProfilesRepository(profile=profile, version=version)
    service.matches = FakeMatchingRepository(active_matches=active_matches)
    service.attempts = FakeAttemptsRepository()
    return service, profile


def test_cv_challenge_service_builds_bootstrap_for_eligible_candidate() -> None:
    service, profile = _build_service()

    bootstrap = service.bootstrap_for_candidate(profile.user_id)

    assert bootstrap["eligible"] is True
    assert bootstrap["challenge"]["title"] == "Helly CV Challenge"
    assert bootstrap["challenge"]["correctSkills"] == ["React", "TypeScript", "Docker"]
    assert bootstrap["attempt"]["id"]
    assert bootstrap["attempt"]["status"] == "started"
    assert bootstrap["lastResult"] is None


def test_cv_challenge_service_rejects_candidate_with_active_matches() -> None:
    service, profile = _build_service(active_matches=[SimpleNamespace(id="match-1")])

    eligibility = service.build_eligibility_for_user_id(profile.user_id)

    assert eligibility.eligible is False
    assert eligibility.reason_code == "candidate_has_active_matches"


def test_cv_challenge_service_finishes_own_attempt_only() -> None:
    service, profile = _build_service()
    bootstrap = service.bootstrap_for_candidate(profile.user_id)

    result = service.finish_attempt(
        user_id=profile.user_id,
        attempt_id=bootstrap["attempt"]["id"],
        score=12,
        lives_left=1,
        stage_reached=3,
        won=True,
        result_json={"missedSkills": ["Docker"]},
    )

    assert result["attempt"]["score"] == 12
    assert result["attempt"]["won"] is True
    assert result["attempt"]["result"]["missedSkills"] == ["Docker"]


def test_cv_challenge_service_reuses_unfinished_attempt_and_shows_last_result() -> None:
    service, profile = _build_service()
    first = service.bootstrap_for_candidate(profile.user_id)
    service.save_attempt_progress(
        user_id=profile.user_id,
        attempt_id=first["attempt"]["id"],
        score=4,
        lives_left=2,
        stage_reached=2,
        progress_json={"score": 4, "stageIndex": 1},
    )

    resumed = service.bootstrap_for_candidate(profile.user_id)

    assert resumed["attempt"]["id"] == first["attempt"]["id"]
    assert resumed["attempt"]["resumable"] is True
    assert resumed["attempt"]["progress"]["score"] == 4

    service.finish_attempt(
        user_id=profile.user_id,
        attempt_id=first["attempt"]["id"],
        score=7,
        lives_left=1,
        stage_reached=3,
        won=False,
        result_json={"totalMistakes": 3},
    )

    next_bootstrap = service.bootstrap_for_candidate(profile.user_id)

    assert next_bootstrap["attempt"]["id"] != first["attempt"]["id"]
    assert next_bootstrap["lastResult"]["score"] == 7
    assert next_bootstrap["lastResult"]["result"]["totalMistakes"] == 3


def test_cv_challenge_service_blocks_foreign_attempt() -> None:
    service, profile = _build_service()
    bootstrap = service.bootstrap_for_candidate(profile.user_id)

    other_service, other_profile = _build_service()
    other_service.attempts = service.attempts

    try:
        other_service.finish_attempt(
            user_id=other_profile.user_id,
            attempt_id=bootstrap["attempt"]["id"],
            score=1,
            lives_left=0,
            stage_reached=1,
            won=False,
            result_json={},
        )
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
