from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from src.webapp.service import WebAppService


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
