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
    ACTIVE_MATCH_STATUSES = {
        "shortlisted",
        "manager_decision_pending",
        "candidate_decision_pending",
        "candidate_applied",
        "manager_interview_requested",
    }

    def __init__(self):
        self.run = None
        self.matches = []
        self.historical_matches = []

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

    def list_all_for_vacancy(self, vacancy_id):
        return [match for match in self.historical_matches if match.vacancy_id == vacancy_id]


def make_candidate(**overrides):
    payload = {
        "id": uuid4(),
        "state": "READY",
        "deleted_at": None,
        "country_code": "PL",
        "city": "Warsaw",
        "work_format": "remote",
        "salary_min": 5000,
        "seniority_normalized": "senior",
        "english_level": "C1",
        "preferred_domains_json": ["saas"],
        "target_role": "Senior Python Backend Developer",
        "show_take_home_task_roles": True,
        "show_live_coding_roles": True,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def make_candidate_version(*, core_skills, years=7, full_skills=None, semantic_embedding=None):
    normalization_json = {"full_hard_skills": full_skills or []}
    return SimpleNamespace(
        id=uuid4(),
        semantic_embedding=semantic_embedding,
        summary_json={"skills": core_skills, "years_experience": years},
        normalization_json=normalization_json,
        extracted_text="",
        transcript_text="",
    )


def make_vacancy(**overrides):
    payload = {
        "id": uuid4(),
        "role_title": "Senior Python Backend Engineer",
        "project_description": "B2B SaaS product for developer analytics.",
        "primary_tech_stack_json": ["python", "postgresql"],
        "countries_allowed_json": ["PL"],
        "work_format": "remote",
        "office_city": None,
        "required_english_level": "B2",
        "has_take_home_task": False,
        "has_live_coding": False,
        "take_home_paid": None,
        "hiring_stages_json": [],
        "budget_max": 7000,
        "seniority_normalized": "senior",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def make_identity_rerank(candidates):
    return SimpleNamespace(
        prompt_version="matching_candidate_rerank_llm_v1",
        payload={
            "ranked_candidates": [
                {
                    "candidate_ref": str(candidate.id),
                    "rank": index,
                    "fit_score": round(1.0 - (index * 0.01), 2),
                    "rationale": "Ranked for test.",
                }
                for index, candidate in enumerate(candidates, start=1)
            ]
        },
    )


def test_execute_for_vacancy_creates_shortlisted_and_filtered_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    vacancy = make_vacancy()
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

    candidate_a = make_candidate()
    candidate_b = make_candidate(country_code="UA")
    candidate_versions = {
        candidate_a.id: make_candidate_version(core_skills=["python", "postgresql"]),
        candidate_b.id: make_candidate_version(core_skills=["python"]),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: make_identity_rerank([candidate_a]),
    )

    result = service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="vacancy_open")

    assert result["candidate_pool_count"] == 2
    assert result["hard_filtered_count"] == 1
    assert result["shortlisted_count"] == 1
    assert any(match.status == "shortlisted" for match in service.matching.matches)
    assert any(match.status == "filtered_out" for match in service.matching.matches)


def test_execute_for_vacancy_applies_new_matching_preferences_as_hard_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vacancy = make_vacancy(
        work_format="hybrid",
        office_city="Warsaw",
        required_english_level="C1",
        has_take_home_task=True,
    )
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)
    candidate = make_candidate(
        city="Krakow",
        work_format="hybrid",
        english_level="B2",
        show_take_home_task_roles=False,
    )
    candidate_versions = {
        candidate.id: make_candidate_version(core_skills=["python"]),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: make_identity_rerank([]),
    )

    result = service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="vacancy_open")

    assert result["hard_filtered_count"] == 1
    match = service.matching.matches[0]
    assert match.status == "filtered_out"
    assert "office_city_mismatch" in match.filter_reason_codes_json
    assert "english_level_mismatch" in match.filter_reason_codes_json
    assert "take_home_preference_mismatch" in match.filter_reason_codes_json


def test_execute_for_vacancy_applies_llm_rerank_to_shortlist(monkeypatch: pytest.MonkeyPatch) -> None:
    vacancy = make_vacancy()
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

    candidate_a = make_candidate(target_role="Senior Python Backend Developer")
    candidate_b = make_candidate(target_role="Senior Python Platform Engineer")
    candidate_versions = {
        candidate_a.id: make_candidate_version(core_skills=["python", "postgresql"]),
        candidate_b.id: make_candidate_version(core_skills=["python", "postgresql"]),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    captured = {}

    def _fake_rerank(*args, **kwargs):
        captured["vacancy_context"] = kwargs["vacancy_context"]
        captured["shortlisted_candidates"] = kwargs["shortlisted_candidates"]
        return SimpleNamespace(
            prompt_version="matching_candidate_rerank_llm_v2",
            payload={
                "ranked_candidates": [
                    {
                        "candidate_ref": str(candidate_b.id),
                        "rank": 1,
                        "fit_score": 0.91,
                        "rationale": "Better direct role fit.",
                        "matched_signals": [
                            "Strong role-title alignment",
                            "Good Python and PostgreSQL overlap",
                        ],
                        "concerns": ["Less explicit backend platform ownership"],
                    },
                    {
                        "candidate_ref": str(candidate_a.id),
                        "rank": 2,
                        "fit_score": 0.82,
                        "rationale": "Strong but slightly less aligned.",
                        "matched_signals": ["Strong backend fit"],
                        "concerns": [],
                    },
                ]
            },
        )

    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        _fake_rerank,
    )

    result = service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="vacancy_open")

    shortlisted = [match for match in service.matching.matches if match.status == "shortlisted"]
    assert result["shortlisted_count"] == 2
    assert len(shortlisted) == 2
    candidate_b_match = next(match for match in shortlisted if match.candidate_profile_id == candidate_b.id)
    candidate_a_match = next(match for match in shortlisted if match.candidate_profile_id == candidate_a.id)
    assert candidate_b_match.llm_rank_position == 1
    assert candidate_a_match.llm_rank_position == 2
    assert candidate_b_match.llm_rank_score == 0.91
    assert candidate_b_match.rationale_json["matched_signals"] == [
        "Strong role-title alignment",
        "Good Python and PostgreSQL overlap",
    ]
    assert candidate_b_match.rationale_json["concerns"] == ["Less explicit backend platform ownership"]
    assert candidate_b_match.rationale_json["fit_band"] in {"strong", "medium", "low"}
    assert isinstance(candidate_b_match.rationale_json["gap_signals"], list)
    assert captured["vacancy_context"]["required_english_level"] == "B2"
    assert captured["vacancy_context"]["vacancy_skill_universe"] == ["python", "postgresql"]
    candidate_payload = next(
        item for item in captured["shortlisted_candidates"] if item["candidate_profile_id"] == candidate_a.id
    )
    assert candidate_payload["candidate_full_hard_skills"] == ["python", "postgresql"]


def test_execute_for_vacancy_does_not_shortlist_not_fit_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    vacancy = make_vacancy(
        role_title="Node.js Developer",
        project_description="Backend platform role using Node.js and Express.",
        primary_tech_stack_json=[
            "node.js",
            "express",
            "mongodb",
            "mongoose",
            "redis",
            "mocha",
            "chai",
            "supertest",
            "git",
            "gcp",
            "rest api",
        ],
        countries_allowed_json=["UA", "PL"],
        required_english_level="B2",
    )
    vacancy_version = SimpleNamespace(
        id=uuid4(),
        semantic_embedding=None,
        extracted_text="Node.js Express MongoDB Mongoose Redis Mocha Chai Supertest Git GCP REST API",
        transcript_text=None,
        approval_summary_text=None,
        summary_json={"primary_tech_stack": vacancy.primary_tech_stack_json},
    )

    candidate_a = make_candidate(
        country_code="UA",
        city="Kyiv",
        work_format="remote",
        english_level="B2",
        target_role="Senior JS Engineer",
        preferred_domains_json=["any"],
    )
    candidate_b = make_candidate(
        country_code="UA",
        city="Kyiv",
        work_format="remote",
        english_level="B2",
        target_role="Senior Backend Engineer",
        preferred_domains_json=["any"],
    )
    candidate_versions = {
        candidate_a.id: make_candidate_version(
            core_skills=["node.js", "express"],
            full_skills=["node.js", "express", "mongodb", "gcp"],
        ),
        candidate_b.id: make_candidate_version(
            core_skills=["mongodb"],
            full_skills=["mongodb", "redis", "python"],
        ),
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate_a, candidate_b], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: SimpleNamespace(
            prompt_version="matching_candidate_rerank_llm_v2",
            payload={
                "ranked_candidates": [
                    {
                        "candidate_ref": str(candidate_a.id),
                        "rank": 1,
                        "fit_score": 0.78,
                        "rationale": "Best available, but partial stack overlap.",
                    },
                    {
                        "candidate_ref": str(candidate_b.id),
                        "rank": 2,
                        "fit_score": 0.42,
                        "rationale": "Broader backend profile, but weak stack fit.",
                    },
                ]
            },
        ),
    )

    result = service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="manager_manual_request")

    shortlisted = [match for match in service.matching.matches if match.status == "shortlisted"]
    filtered = [match for match in service.matching.matches if match.status == "filtered_out"]

    assert result["candidate_pool_count"] == 2
    assert result["hard_filtered_count"] == 0
    assert result["shortlisted_count"] == 0
    assert shortlisted == []
    assert len(filtered) == 2
    assert {match.filter_reason_codes_json[0] for match in filtered} == {"below_fit_band_cutoff"}
    assert {match.rationale_json["fit_band"] for match in filtered} == {"not_fit"}


def test_execute_for_vacancy_uses_hybrid_vector_pool_and_skill_rescue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vacancy = make_vacancy(
        primary_tech_stack_json=["python"],
    )
    vacancy_version = SimpleNamespace(
        id=uuid4(),
        semantic_embedding=AmbiguousEmbedding(0.1, 0.2, 0.3),
        extracted_text="Senior Django backend role using Python, Django and PostgreSQL.",
        transcript_text=None,
        approval_summary_text=None,
        summary_json={"primary_tech_stack": ["python"]},
    )

    candidate_vector = make_candidate(target_role="Python Developer")
    candidate_skill = make_candidate(target_role="Django Backend Developer")
    candidate_versions = {
        candidate_vector.id: make_candidate_version(
            core_skills=["python"],
            full_skills=["python"],
            semantic_embedding=[0.1, 0.2, 0.29],
        ),
        candidate_skill.id: make_candidate_version(
            core_skills=["python"],
            full_skills=["python", "django", "postgresql"],
            semantic_embedding=[0.01, 0.02, 0.03],
        ),
    }

    service = MatchingService(FakeSession())
    fake_candidates = FakeCandidateRepository([candidate_vector, candidate_skill], candidate_versions)
    fake_candidates.similar_results = [
        {
            "candidate": candidate_vector,
            "candidate_version": candidate_versions[candidate_vector.id],
            "embedding_score": 0.97,
        },
    ]
    service.candidates = fake_candidates
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: make_identity_rerank([candidate_skill, candidate_vector]),
    )

    result = service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="vacancy_open")

    shortlisted_ids = {
        match.candidate_profile_id
        for match in service.matching.matches
        if match.status == "shortlisted"
    }
    assert result["candidate_pool_count"] == 2
    assert service.matching.run.payload_json["mode"] == "hybrid_vector_plus_deterministic_plus_llm_rerank"
    assert service.matching.run.payload_json["vacancy_skill_count"] >= 3
    assert service.matching.run.payload_json["hybrid_skill_pool_count"] == 2
    assert candidate_skill.id in shortlisted_ids


def test_execute_for_vacancy_carries_feedback_categories_into_rationale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vacancy = make_vacancy(
        questions_context_json={
            "matching_feedback": {
                "manager_feedback_events": [
                    {"categories": ["stack", "english"], "text": "Need stronger stack and English."}
                ]
            }
        }
    )
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

    candidate = make_candidate(
        questions_context_json={
            "matching_feedback": {
                "candidate_feedback_events": [
                    {"categories": ["process"], "text": "I keep skipping heavy processes."}
                ]
            }
        }
    )
    candidate_versions = {
        candidate.id: make_candidate_version(core_skills=["python", "postgresql"], full_skills=["python", "postgresql"])
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: make_identity_rerank([candidate]),
    )

    service.execute_for_vacancy(vacancy_id=vacancy.id, trigger_type="vacancy_open")

    shortlisted = [match for match in service.matching.matches if match.status == "shortlisted"]
    assert len(shortlisted) == 1
    rationale = shortlisted[0].rationale_json
    assert rationale["feedback_categories"] == ["process", "stack", "english"]
    assert rationale["score_breakdown"]["feedback_fit"] > 0.0


def test_execute_for_vacancy_skips_candidate_seen_for_same_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vacancy = make_vacancy(primary_tech_stack_json=["node.js", "postgresql"], countries_allowed_json=["UA"])
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

    seen_candidate = make_candidate(country_code="UA", target_role="Senior Node.js Engineer")
    fresh_candidate = make_candidate(country_code="UA", target_role="Senior Node.js Engineer")
    seen_version = make_candidate_version(core_skills=["node.js", "postgresql"])
    fresh_version = make_candidate_version(core_skills=["node.js", "postgresql"])
    candidate_versions = {
        seen_candidate.id: seen_version,
        fresh_candidate.id: fresh_version,
    }

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([seen_candidate, fresh_candidate], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    service.matching.historical_matches = [
        SimpleNamespace(
            vacancy_id=vacancy.id,
            candidate_profile_id=seen_candidate.id,
            candidate_profile_version_id=seen_version.id,
            vacancy_version_id=vacancy_version.id,
            status="candidate_skipped",
        )
    ]
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: make_identity_rerank([fresh_candidate]),
    )

    result = service.execute_for_vacancy(
        vacancy_id=vacancy.id,
        trigger_type="manager_manual_request",
    )

    shortlisted_ids = {
        match.candidate_profile_id
        for match in service.matching.matches
        if match.status == "shortlisted"
    }
    assert result["candidate_pool_count"] == 1
    assert fresh_candidate.id in shortlisted_ids
    assert seen_candidate.id not in shortlisted_ids


def test_execute_for_vacancy_resurfaces_candidate_after_profile_version_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vacancy = make_vacancy(primary_tech_stack_json=["node.js", "postgresql"], countries_allowed_json=["UA"])
    vacancy_version = SimpleNamespace(id=uuid4(), semantic_embedding=None)

    candidate = make_candidate(country_code="UA", target_role="Senior Node.js Engineer")
    current_version = make_candidate_version(
        core_skills=["node.js"],
        full_skills=["node.js", "postgresql"],
    )
    old_version = make_candidate_version(core_skills=["node.js"])
    candidate_versions = {candidate.id: current_version}

    service = MatchingService(FakeSession())
    service.candidates = FakeCandidateRepository([candidate], candidate_versions)
    service.vacancies = FakeVacancyRepository(vacancy, vacancy_version)
    service.matching = FakeMatchingRepository()
    service.matching.historical_matches = [
        SimpleNamespace(
            vacancy_id=vacancy.id,
            candidate_profile_id=candidate.id,
            candidate_profile_version_id=old_version.id,
            vacancy_version_id=vacancy_version.id,
            status="candidate_skipped",
        )
    ]
    monkeypatch.setattr(
        "src.matching.service.safe_rerank_candidates",
        lambda *args, **kwargs: make_identity_rerank([candidate]),
    )

    result = service.execute_for_vacancy(
        vacancy_id=vacancy.id,
        trigger_type="manager_manual_request",
    )

    shortlisted_ids = {
        match.candidate_profile_id
        for match in service.matching.matches
        if match.status == "shortlisted"
    }
    assert result["candidate_pool_count"] == 1
    assert shortlisted_ids == {candidate.id}
