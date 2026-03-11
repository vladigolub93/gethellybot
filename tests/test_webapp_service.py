from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from src.webapp.service import WebAppService


class FakeSession:
    def __init__(self):
        self.commit_calls = 0

    def commit(self):
        self.commit_calls += 1


class FakeCandidateProfilesRepository:
    def __init__(self, profile, version):
        self.profile = profile
        self.version = version

    def get_active_by_user_id(self, _user_id):
        return self.profile

    def get_current_version(self, _profile):
        return self.version


class FakeMatchingRepository:
    def __init__(self, matches):
        self.matches = list(matches)

    def list_all_for_candidate(self, _candidate_profile_id):
        return list(self.matches)


class FakeVacanciesRepository:
    def __init__(self, vacancy):
        self.vacancy = vacancy

    def get_by_id(self, _vacancy_id):
        return self.vacancy


class FakeInterviewsRepository:
    def __init__(self, interview):
        self.interview = interview

    def get_session_by_match_id(self, _match_id):
        return self.interview


class FakeCvChallengeService:
    def __init__(self, response):
        self.response = response
        self.called_user_id = None

    def build_dashboard_card(self, user_id):
        self.called_user_id = user_id
        return dict(self.response)


class FakeCvChallengeWriteService:
    def __init__(self, bootstrap_response=None, finish_response=None):
        self.bootstrap_response = bootstrap_response or {}
        self.finish_response = finish_response or {}
        self.bootstrap_user_id = None
        self.finish_payload = None
        self.progress_payload = None

    def bootstrap_for_candidate(self, user_id):
        self.bootstrap_user_id = user_id
        return dict(self.bootstrap_response)

    def finish_attempt(self, **kwargs):
        self.finish_payload = dict(kwargs)
        return dict(self.finish_response)

    def save_attempt_progress(self, **kwargs):
        self.progress_payload = dict(kwargs)
        return {
            "attempt": {
                "id": kwargs["attempt_id"],
                "status": "started",
                "score": kwargs["score"],
                "livesLeft": kwargs["lives_left"],
                "stageReached": kwargs["stage_reached"],
                "progress": kwargs["progress_json"],
            }
        }


def test_list_candidate_opportunities_includes_challenge_card_and_serialized_matches() -> None:
    user_id = uuid4()
    profile_id = uuid4()
    vacancy_id = uuid4()
    match_id = uuid4()
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)

    service = WebAppService(session=object())
    service.candidate_profiles = FakeCandidateProfilesRepository(
        profile=SimpleNamespace(
            id=profile_id,
            user_id=user_id,
            state="READY",
            location_text="Kyiv",
            country_code="UA",
            work_format="remote",
            salary_min=5000,
            salary_max=6000,
            salary_currency="USD",
            salary_period="month",
            ready_at=now,
            updated_at=now,
        ),
        version=SimpleNamespace(
            summary_json={
                "headline": "Senior Full-Stack Engineer",
                "approval_summary_text": "Built fintech and climate tech products.",
                "skills": ["React", "TypeScript", "Node.js"],
                "years_experience": 10,
                "target_role": "Senior Full-Stack Engineer",
            }
        ),
    )
    service.matches = FakeMatchingRepository(
        matches=[
            SimpleNamespace(
                id=match_id,
                vacancy_id=vacancy_id,
                status="candidate_decision_pending",
                updated_at=now,
            )
        ]
    )
    service.vacancies = FakeVacanciesRepository(
        vacancy=SimpleNamespace(
            id=vacancy_id,
            role_title="Senior Backend Engineer",
            budget_min=6000,
            budget_max=7000,
            budget_currency="USD",
            budget_period="month",
            work_format="remote",
        )
    )
    service.interviews = FakeInterviewsRepository(
        interview=SimpleNamespace(
            state="INVITED",
        )
    )
    service.cv_challenge = FakeCvChallengeService(
        response={
            "eligible": True,
            "title": "Helly CV Challenge",
            "launchUrl": "https://helly.test/webapp/cv-challenge",
        }
    )

    payload = service.list_candidate_opportunities(
        SimpleNamespace(
            role="candidate",
            user_id=str(user_id),
        )
    )

    assert str(service.cv_challenge.called_user_id) == str(user_id)
    assert payload["cvChallenge"]["eligible"] is True
    assert payload["profile"]["location"] == "Kyiv"
    assert payload["items"] == [
        {
            "id": str(match_id),
            "vacancyId": str(vacancy_id),
            "roleTitle": "Senior Backend Engineer",
            "budget": "6000-7000 USD per month",
            "workFormat": "remote",
            "stage": "candidate_decision_pending",
            "stageLabel": "Waiting for candidate reply",
            "interviewState": "INVITED",
            "interviewStateLabel": "Invited",
            "updatedAt": now.isoformat(),
        }
    ]


def test_bootstrap_candidate_cv_challenge_commits_only_for_eligible_attempts() -> None:
    session = FakeSession()
    user_id = uuid4()
    service = WebAppService(session=session)
    service.cv_challenge = FakeCvChallengeWriteService(
        bootstrap_response={
            "eligible": True,
            "attempt": {"id": "attempt-1"},
            "challenge": {"title": "Helly CV Challenge"},
        }
    )

    response = service.bootstrap_candidate_cv_challenge(
        SimpleNamespace(role="candidate", user_id=str(user_id))
    )

    assert response["attempt"]["id"] == "attempt-1"
    assert str(service.cv_challenge.bootstrap_user_id) == str(user_id)
    assert session.commit_calls == 1

    ineligible_service = WebAppService(session=FakeSession())
    ineligible_service.cv_challenge = FakeCvChallengeWriteService(
        bootstrap_response={
            "eligible": False,
            "reasonCode": "candidate_has_active_matches",
        }
    )
    response = ineligible_service.bootstrap_candidate_cv_challenge(
        SimpleNamespace(role="candidate", user_id=str(user_id))
    )

    assert response["eligible"] is False
    assert ineligible_service.session.commit_calls == 0


def test_finish_candidate_cv_challenge_commits_result() -> None:
    session = FakeSession()
    user_id = uuid4()
    service = WebAppService(session=session)
    service.cv_challenge = FakeCvChallengeWriteService(
        finish_response={
            "attempt": {
                "id": "attempt-1",
                "status": "completed",
                "score": 9,
                "won": False,
            }
        }
    )

    response = service.finish_candidate_cv_challenge(
        SimpleNamespace(role="candidate", user_id=str(user_id)),
        attempt_id="attempt-1",
        score=9,
        lives_left=1,
        stage_reached=3,
        won=False,
        result_json={"missedSkills": ["Docker"]},
    )

    assert response["attempt"]["status"] == "completed"
    assert str(service.cv_challenge.finish_payload["user_id"]) == str(user_id)
    assert service.cv_challenge.finish_payload["attempt_id"] == "attempt-1"
    assert session.commit_calls == 1


def test_save_candidate_cv_challenge_progress_commits_result() -> None:
    session = FakeSession()
    user_id = uuid4()
    service = WebAppService(session=session)
    service.cv_challenge = FakeCvChallengeWriteService()

    response = service.save_candidate_cv_challenge_progress(
        SimpleNamespace(role="candidate", user_id=str(user_id)),
        attempt_id="attempt-2",
        score=5,
        lives_left=2,
        stage_reached=2,
        progress_json={"score": 5, "objects": [{"text": "React"}]},
    )

    assert response["attempt"]["status"] == "started"
    assert str(service.cv_challenge.progress_payload["user_id"]) == str(user_id)
    assert service.cv_challenge.progress_payload["attempt_id"] == "attempt-2"
    assert session.commit_calls == 1
