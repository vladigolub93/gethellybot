from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.matching.service import MatchingService


class FakeSession:
    pass


class AmbiguousEmbedding:
    def __init__(self, *values: float) -> None:
        self.values = list(values)

    def __iter__(self):
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __bool__(self) -> bool:
        raise ValueError("The truth value of an array with more than one element is ambiguous.")


class FakeCandidateRepository:
    def __init__(self, candidates, versions):
        self.candidates = {candidate.id: candidate for candidate in candidates}
        self.versions = versions
        self.similar_results = []

    def get_by_id(self, profile_id):
        return self.candidates.get(profile_id)

    def get_ready_profiles(self):
        return list(self.candidates.values())

    def get_current_version(self, candidate):
        return self.versions[candidate.id]

    def list_top_similar_ready_profiles(self, *, embedding, limit=50):
        return self.similar_results[:limit]


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
        self.active_matches = []

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

    def list_active_for_vacancy(self, vacancy_id):
        return [match for match in self.active_matches if match.vacancy_id == vacancy_id]


def test_execute_for_vacancy_creates_shortlisted_and_filtered_matches() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        primary_tech_stack_json=["python", "postgresql"],
        countries_allowed_json=["PL"],
        work_format="remote",
        budget_max=6000,
        seniority_normalized="senior",
    )
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

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
            semantic_embedding=None,
            summary_json={"skills": ["python", "postgresql"], "years_experience": 7},
        ),
        candidate_b.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=None,
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


def test_execute_for_vacancy_applies_llm_rerank_to_shortlist(monkeypatch: pytest.MonkeyPatch) -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        primary_tech_stack_json=["python", "postgresql"],
        countries_allowed_json=["PL"],
        work_format="remote",
        budget_max=6000,
        seniority_normalized="senior",
    )
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

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
        country_code="PL",
        work_format="remote",
        salary_min=5000,
        seniority_normalized="senior",
    )
    candidate_versions = {
        candidate_a.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=None,
            summary_json={"skills": ["python", "postgresql"], "years_experience": 7},
        ),
        candidate_b.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=None,
            summary_json={"skills": ["python", "postgresql"], "years_experience": 7},
        ),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()

    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: SimpleNamespace(
            prompt_version="matching_candidate_rerank_llm_v1",
            payload={
                "ranked_candidates": [
                    {
                        "candidate_ref": str(candidate_b.id),
                        "rank": 1,
                        "fit_score": 0.91,
                        "rationale": "Better direct role fit.",
                    },
                    {
                        "candidate_ref": str(candidate_a.id),
                        "rank": 2,
                        "fit_score": 0.82,
                        "rationale": "Strong but slightly less aligned.",
                    },
                ]
            },
        ),
    )

    result = service.execute_for_vacancy(
        vacancy_id=vacancy.id,
        trigger_type="vacancy_open",
    )

    shortlisted = [match for match in service.matching.matches if match.status == "shortlisted"]
    assert result["shortlisted_count"] == 2
    assert len(shortlisted) == 2
    candidate_b_match = next(match for match in shortlisted if match.candidate_profile_id == candidate_b.id)
    candidate_a_match = next(match for match in shortlisted if match.candidate_profile_id == candidate_a.id)
    assert candidate_b_match.llm_rank_position == 1
    assert candidate_a_match.llm_rank_position == 2
    assert candidate_b_match.llm_rank_score == 0.91


def test_execute_for_vacancy_uses_vector_retrieval_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        primary_tech_stack_json=["python", "postgresql"],
        countries_allowed_json=["PL"],
        work_format="remote",
        budget_max=6000,
        seniority_normalized="senior",
    )
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=AmbiguousEmbedding(0.1, 0.2, 0.3))

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
        country_code="PL",
        work_format="remote",
        salary_min=5000,
        seniority_normalized="senior",
    )
    candidate_versions = {
        candidate_a.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=[0.1, 0.2, 0.29],
            summary_json={"skills": ["python"], "years_experience": 7},
        ),
        candidate_b.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=[0.05, 0.1, 0.15],
            summary_json={"skills": ["postgresql"], "years_experience": 5},
        ),
    }

    service = MatchingService(FakeSession())
    fake_candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    fake_candidates.similar_results = [
        {
            "candidate": candidate_a,
            "candidate_version": candidate_versions[candidate_a.id],
            "embedding_score": 0.97,
        },
        {
            "candidate": candidate_b,
            "candidate_version": candidate_versions[candidate_b.id],
            "embedding_score": 0.82,
        },
    ]
    service.candidates = fake_candidates
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()

    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: SimpleNamespace(
            prompt_version="matching_candidate_rerank_llm_v1",
            payload={
                "ranked_candidates": [
                    {"candidate_ref": str(candidate_a.id), "rank": 1, "fit_score": 0.93, "rationale": "Closer stack fit."},
                    {"candidate_ref": str(candidate_b.id), "rank": 2, "fit_score": 0.81, "rationale": "Good secondary fit."},
                ]
            },
        ),
    )

    result = service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="vacancy_open")

    assert result["candidate_pool_count"] == 2
    assert service.matching.run.payload_json["mode"] == "vector_plus_deterministic_plus_llm_rerank"
    shortlisted = [match for match in service.matching.matches if match.status == "shortlisted"]
    assert shortlisted[0].embedding_score == 0.97


def test_execute_for_vacancy_skips_candidates_with_active_matches() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        primary_tech_stack_json=["python", "postgresql"],
        countries_allowed_json=["PL"],
        work_format="remote",
        budget_max=6000,
        seniority_normalized="senior",
    )
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

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
        country_code="PL",
        work_format="remote",
        salary_min=5000,
        seniority_normalized="senior",
    )
    candidate_versions = {
        candidate_a.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=None,
            summary_json={"skills": ["python", "postgresql"], "years_experience": 7},
        ),
        candidate_b.id: SimpleNamespace(
            id=uuid4(),
            semantic_embedding=None,
            summary_json={"skills": ["python", "postgresql"], "years_experience": 7},
        ),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    service.matching.active_matches.append(
        SimpleNamespace(vacancy_id=vacancy.id, candidate_profile_id=candidate_a.id, status="invited")
    )

    result = service.execute_for_vacancy(
        vacancy_id=vacancy.id,
        trigger_type="manager_manual_request",
    )

    assert result["candidate_pool_count"] == 1
    assert result["shortlisted_count"] == 1
    shortlisted = [match for match in service.matching.matches if match.status == "shortlisted"]
    assert len(shortlisted) == 1
    assert shortlisted[0].candidate_profile_id == candidate_b.id
