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

    def get_by_id(self, _profile_id):
        return self.profile


class FakeMatchingRepository:
    ACTIVE_MATCH_STATUSES = frozenset(
        {
            "shortlisted",
            "manager_decision_pending",
            "candidate_decision_pending",
            "candidate_applied",
            "manager_interview_requested",
        }
    )

    def __init__(self, matches):
        self.matches = list(matches)

    def list_all_for_candidate(self, _candidate_profile_id):
        return list(self.matches)

    def list_all_for_vacancy(self, _vacancy_id):
        return list(self.matches)

    def get_by_id(self, match_id):
        for match in self.matches:
            if str(match.id) == str(match_id):
                return match
        return None


class FakeVacanciesRepository:
    def __init__(self, vacancy, *, version=None):
        self.vacancy = vacancy
        self.version = version

    def get_by_id(self, _vacancy_id):
        return self.vacancy

    def get_by_manager_user_id(self, _user_id):
        return [self.vacancy]

    def get_current_version(self, _vacancy):
        return self.version


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


class FakeUsersRepository:
    def __init__(self, users_by_id):
        self.users_by_id = dict(users_by_id)

    def get_by_id(self, user_id):
        return self.users_by_id.get(str(user_id))


class FakeEvaluationsRepository:
    def __init__(self, evaluation):
        self.evaluation = evaluation

    def get_by_match_id(self, _match_id):
        return self.evaluation


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
            office_city=None,
            required_english_level="B2",
            hiring_stages_json=["recruiter_screen", "technical_interview", "final"],
            has_take_home_task=True,
            has_live_coding=False,
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
            "officeCity": None,
            "requiredEnglishLevel": "B2",
            "hiringStages": ["Recruiter screen", "Technical interview", "Final interview"],
            "hasTakeHomeTask": True,
            "hasLiveCoding": False,
            "stage": "candidate_decision_pending",
            "stageLabel": "Your reply",
            "stageDescription": "Your reply is needed to keep this opportunity moving.",
            "needsAction": True,
            "updatedAt": now.isoformat(),
        }
    ]


def test_candidate_profile_detail_includes_summary_answers_and_source_text() -> None:
    user_id = uuid4()
    profile_id = uuid4()
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)

    service = WebAppService(session=object())
    service.candidate_profiles = FakeCandidateProfilesRepository(
        profile=SimpleNamespace(
            id=profile_id,
            user_id=user_id,
            state="READY",
            location_text="Kyiv",
            country_code="UA",
            city="Kyiv",
            work_format="remote",
            english_level="B2",
            preferred_domains_json=["fintech", "saas"],
            show_take_home_task_roles=True,
            show_live_coding_roles=False,
            salary_min=5000,
            salary_max=6000,
            salary_currency="USD",
            salary_period="month",
            ready_at=now,
            updated_at=now,
        ),
        version=SimpleNamespace(
            source_type="cv_file",
            extracted_text="Senior backend engineer with Node.js and PostgreSQL background.",
            transcript_text=None,
            summary_json={
                "headline": "Senior Backend Engineer",
                "approval_summary_text": "Built scalable backend products.",
                "skills": ["Node.js", "PostgreSQL"],
                "years_experience": 8,
                "target_role": "Backend Engineer",
            },
        ),
    )
    service.users = FakeUsersRepository(
        {
            str(user_id): SimpleNamespace(
                id=user_id,
                display_name="Candidate Name",
                username="candidate_name",
            )
        }
    )

    payload = service.get_candidate_profile_detail(
        SimpleNamespace(
            role="candidate",
            user_id=str(user_id),
        )
    )

    assert payload["profile"]["name"] == "Candidate Name"
    assert payload["profile"]["summary"]["approvalSummaryText"] == "Built scalable backend products."
    assert payload["profile"]["fullHardSkills"] == ["Node.js", "PostgreSQL"]
    assert payload["profile"]["answers"] == {
        "salaryExpectation": "5000-6000 USD per month",
        "location": "Kyiv",
        "countryCode": "UA",
        "city": "Kyiv",
        "workFormat": "remote",
        "englishLevel": "B2",
        "preferredDomains": ["Fintech", "SaaS"],
        "showTakeHomeTaskRoles": True,
        "showLiveCodingRoles": False,
    }
    assert payload["profile"]["source"]["sourceType"] == "cv_file"
    assert payload["profile"]["source"]["text"] == "Senior backend engineer with Node.js and PostgreSQL background."


def test_candidate_opportunity_detail_includes_why_this_role() -> None:
    user_id = uuid4()
    manager_user_id = uuid4()
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
            city="Kyiv",
            work_format="remote",
            salary_min=5000,
            salary_max=6000,
            salary_currency="USD",
            salary_period="month",
            ready_at=now,
            updated_at=now,
        ),
        version=SimpleNamespace(
            source_type="cv_file",
            extracted_text="Senior backend engineer with Node.js and PostgreSQL background.",
            transcript_text=None,
            summary_json={
                "headline": "Senior Backend Engineer",
                "approval_summary_text": "Built scalable backend products.",
                "skills": ["Node.js", "PostgreSQL"],
                "years_experience": 8,
                "target_role": "Senior Backend Engineer",
            },
        ),
    )
    service.matches = FakeMatchingRepository(
        matches=[
            SimpleNamespace(
                id=match_id,
                vacancy_id=vacancy_id,
                candidate_profile_id=profile_id,
                status="candidate_decision_pending",
                updated_at=now,
                invitation_sent_at=None,
                candidate_response_at=None,
                manager_decision_at=None,
            )
        ]
    )
    service.vacancies = FakeVacanciesRepository(
        vacancy=SimpleNamespace(
            id=vacancy_id,
            manager_user_id=manager_user_id,
            role_title="Senior Backend Engineer",
            budget_min=6000,
            budget_max=7000,
            budget_currency="USD",
            budget_period="month",
            countries_allowed_json=["UA"],
            work_format="remote",
            team_size="8",
            project_description="Realtime pricing platform",
            primary_tech_stack_json=["Node.js", "PostgreSQL"],
            seniority_normalized="senior",
            opened_at=now,
            updated_at=now,
        ),
        version=SimpleNamespace(
            source_type="job_description",
            extracted_text="Senior Node.js role for a realtime pricing platform.",
            transcript_text=None,
            summary_json={
                "approval_summary_text": "Build and run a pricing platform.",
                "headline": "Senior Node.js role",
                "skills": ["Node.js", "PostgreSQL"],
            },
        ),
    )
    service.users = FakeUsersRepository({})
    service.interviews = FakeInterviewsRepository(interview=None)
    service.evaluations = FakeEvaluationsRepository(evaluation=None)

    payload = service.get_candidate_opportunity_detail(
        SimpleNamespace(role="candidate", user_id=str(user_id)),
        str(match_id),
    )

    assert payload["vacancy"]["whyThisRole"] == (
        "Your profile overlaps with this role on Node.js, PostgreSQL. "
        "It also matches your preferred work format: remote."
    )


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


def test_manager_webapp_payloads_follow_direct_contact_flow() -> None:
    manager_user_id = uuid4()
    candidate_user_id = uuid4()
    profile_id = uuid4()
    vacancy_id = uuid4()
    match_id = uuid4()
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)

    vacancy = SimpleNamespace(
        id=vacancy_id,
        manager_user_id=manager_user_id,
        role_title="Node.js Developer",
        state="OPEN",
        budget_min=6000,
        budget_max=7000,
        budget_currency="USD",
        budget_period="month",
        countries_allowed_json=["UA"],
        work_format="remote",
        office_city=None,
        required_english_level="B2",
        hiring_stages_json=["recruiter_screen", "technical_interview", "final"],
        has_take_home_task=True,
        take_home_paid=False,
        has_live_coding=False,
        team_size="8",
        project_description="Realtime pricing platform",
        primary_tech_stack_json=["Node.js", "PostgreSQL"],
        seniority_normalized="senior",
        opened_at=now,
        updated_at=now,
    )
    service = WebAppService(session=object())
    service.vacancies = FakeVacanciesRepository(
        vacancy=vacancy,
        version=SimpleNamespace(
            source_type="job_description",
            extracted_text="Senior Node.js role for a realtime pricing platform.",
            transcript_text=None,
            summary_json={
                "approval_summary_text": "Build and run a pricing platform.",
                "headline": "Senior Node.js role",
                "skills": ["Node.js", "PostgreSQL"],
            }
        ),
    )
    service.matches = FakeMatchingRepository(
        matches=[
            SimpleNamespace(
                id=match_id,
                vacancy_id=vacancy_id,
                candidate_profile_id=profile_id,
                status="approved",
                updated_at=now,
                invitation_sent_at=now,
                candidate_response_at=now,
                manager_decision_at=now,
            )
        ]
    )
    service.candidate_profiles = FakeCandidateProfilesRepository(
        profile=SimpleNamespace(
            id=profile_id,
            user_id=candidate_user_id,
            location_text="Kyiv",
            country_code="UA",
            city="Kyiv",
            work_format="remote",
            english_level="C1",
            preferred_domains_json=["any"],
            show_take_home_task_roles=True,
            show_live_coding_roles=False,
            salary_min=5000,
            salary_max=6000,
            salary_currency="USD",
            salary_period="month",
        ),
        version=SimpleNamespace(
            source_type="cv_file",
            extracted_text="Built scalable Node.js backends for product teams.",
            transcript_text=None,
            summary_json={
                "approval_summary_text": "Built scalable Node.js backends.",
                "skills": ["Node.js", "TypeScript"],
            }
        ),
    )
    service.users = FakeUsersRepository(
        {
            str(manager_user_id): SimpleNamespace(
                id=manager_user_id,
                display_name="Manager Name",
                username="manager_name",
            ),
            str(candidate_user_id): SimpleNamespace(
                id=candidate_user_id,
                display_name="Candidate Name",
                username="candidate_name",
            ),
        }
    )
    service.interviews = FakeInterviewsRepository(interview=None)
    service.evaluations = FakeEvaluationsRepository(evaluation=None)

    session_context = SimpleNamespace(role="hiring_manager", user_id=str(manager_user_id))

    vacancies_payload = service.list_manager_vacancies(session_context)
    matches_payload = service.list_manager_vacancy_matches(session_context, str(vacancy_id))
    match_detail_payload = service.get_manager_match_detail(session_context, str(match_id))

    assert vacancies_payload["items"] == [
        {
            "id": str(vacancy_id),
            "roleTitle": "Node.js Developer",
            "state": "OPEN",
            "budget": "6000-7000 USD per month",
            "candidateCount": 1,
            "activePipelineCount": 0,
            "needsReviewCount": 0,
            "interviewCount": 0,
            "connectedCount": 1,
            "updatedAt": now.isoformat(),
        }
    ]
    assert matches_payload["items"] == [
        {
            "id": str(match_id),
            "candidateProfileId": str(profile_id),
            "candidateName": "Candidate Name",
            "location": "Kyiv",
            "salaryExpectation": "5000-6000 USD per month",
            "workFormat": "remote",
            "englishLevel": "C1",
            "preferredDomains": ["Any domain"],
            "stage": "approved",
            "stageLabel": "Connected",
            "stageDescription": "Contacts were shared and this candidate moved into direct communication.",
            "needsAction": False,
            "summary": {
                "headline": None,
                "approvalSummaryText": "Built scalable Node.js backends.",
                "skills": ["Node.js", "TypeScript"],
                "yearsExperience": None,
                "targetRole": None,
                "experienceExcerpt": None,
            },
            "updatedAt": now.isoformat(),
        }
    ]
    assert match_detail_payload["match"]["statusLabel"] == "Connected"
    assert match_detail_payload["match"]["statusDescription"] == "Contacts were shared and this candidate moved into direct communication."
    assert match_detail_payload["match"]["needsCandidateAction"] is False
    assert match_detail_payload["match"]["needsManagerAction"] is False
    assert match_detail_payload["vacancy"]["whyThisRole"] == (
        "Your profile overlaps with this role on Node.js. "
        "It also matches your preferred work format: remote."
    )
    assert match_detail_payload["vacancy"]["requiredEnglishLevel"] == "B2"
    assert match_detail_payload["vacancy"]["hiringStages"] == ["Recruiter screen", "Technical interview", "Final interview"]
    assert match_detail_payload["vacancy"]["hasTakeHomeTask"] is True
    assert match_detail_payload["vacancy"]["takeHomePaid"] is False
    assert match_detail_payload["vacancy"]["hasLiveCoding"] is False
    assert match_detail_payload["vacancy"]["source"]["text"] == "Senior Node.js role for a realtime pricing platform."
    assert match_detail_payload["candidate"]["answers"]["city"] == "Kyiv"
    assert match_detail_payload["candidate"]["answers"]["englishLevel"] == "C1"
    assert match_detail_payload["candidate"]["answers"]["preferredDomains"] == ["Any domain"]
    assert match_detail_payload["candidate"]["answers"]["showTakeHomeTaskRoles"] is True
    assert match_detail_payload["candidate"]["answers"]["showLiveCodingRoles"] is False
    assert match_detail_payload["candidate"]["fullHardSkills"] == ["Node.js", "TypeScript"]
    assert match_detail_payload["candidate"]["source"]["text"] == "Built scalable Node.js backends for product teams."
    assert match_detail_payload["interview"]["state"] is None
    assert match_detail_payload["evaluation"]["interviewSummary"] is None


def test_manager_vacancy_cards_include_review_and_interview_counts() -> None:
    manager_user_id = uuid4()
    vacancy_id = uuid4()
    now = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)

    service = WebAppService(session=object())
    service.vacancies = FakeVacanciesRepository(
        vacancy=SimpleNamespace(
            id=vacancy_id,
            manager_user_id=manager_user_id,
            role_title="Node.js Developer",
            state="OPEN",
            budget_min=6000,
            budget_max=7000,
            budget_currency="USD",
            budget_period="month",
            updated_at=now,
        )
    )
    service.matches = FakeMatchingRepository(
        matches=[
            SimpleNamespace(
                id=uuid4(),
                vacancy_id=vacancy_id,
                candidate_profile_id=uuid4(),
                status="manager_decision_pending",
                updated_at=now,
            ),
            SimpleNamespace(
                id=uuid4(),
                vacancy_id=vacancy_id,
                candidate_profile_id=uuid4(),
                status="invited",
                updated_at=now,
            ),
        ]
    )

    payload = service.list_manager_vacancies(
        SimpleNamespace(role="hiring_manager", user_id=str(manager_user_id))
    )

    assert payload["items"][0]["needsReviewCount"] == 1
    assert payload["items"][0]["interviewCount"] == 1
