from types import SimpleNamespace
from uuid import uuid4

from src.matching.service import MatchingService


class FakeSession:
    pass


class FakeCandidateRepository:
    def __init__(self, candidates, versions):
        self.candidates = {candidate.id: candidate for candidate in candidates}
        self.versions = versions

    def get_by_id(self, profile_id):
        return self.candidates.get(profile_id)

    def get_ready_profiles(self):
        return list(self.candidates.values())

    def get_current_version(self, candidate):
        return self.versions[candidate.id]


class FakeVacancyRepository:
    def __init__(self, vacancy, version):
        self.vacancy = vacancy
        self.version = version

    def get_by_id(self, vacancy_id):
        return self.vacancy if self.vacancy.id == vacancy_id else None

    def get_current_version(self, _vacancy):
        return self.version


class FakeMatchingRepository:
    def __init__(self):
        self.run = None
        self.matches = []

    def create_run(self, **kwargs):
        self.run = SimpleNamespace(id=uuid4(), **kwargs)
        return self.run

    def create_match(self, **kwargs):
        self.matches.append(SimpleNamespace(**kwargs))
        return self.matches[-1]

    def update_run_counts(self, run, **kwargs):
        for key, value in kwargs.items():
            setattr(run, key, value)
        return run


def test_execute_for_vacancy_creates_shortlisted_and_filtered_matches() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        primary_tech_stack_json=["python", "postgresql"],
        countries_allowed_json=["PL"],
        work_format="remote",
        budget_max=6000,
        seniority_normalized="senior",
    )
    vacancy_version = SimpleNamespace(id=uuid4())

    candidate_a = SimpleNamespace(
        id=uuid4(),
        state="READY",
        deleted_at=None,
        country_code="PL",
        work_format="remote",
        salary_min=5000,
        seniority_normalized="senior",
    )
    candidate_b = SimpleNamespace(
        id=uuid4(),
        state="READY",
        deleted_at=None,
        country_code="UA",
        work_format="remote",
        salary_min=5000,
        seniority_normalized="senior",
    )
    candidate_versions = {
        candidate_a.id: SimpleNamespace(
            id=uuid4(),
            summary_json={"skills": ["python", "postgresql"], "years_experience": 7},
        ),
        candidate_b.id: SimpleNamespace(
            id=uuid4(),
            summary_json={"skills": ["python"], "years_experience": 4},
        ),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()

    result = service.execute_for_vacancy(
        vacancy_id=vacancy.id,
        trigger_type="vacancy_open",
    )

    assert result["candidate_pool_count"] == 2
    assert result["hard_filtered_count"] == 1
    assert result["shortlisted_count"] == 1
    assert len(service.matching.matches) == 2
    assert any(match.status == "shortlisted" for match in service.matching.matches)
    assert any(match.status == "filtered_out" for match in service.matching.matches)
