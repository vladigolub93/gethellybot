from src.matching.scoring import (
    build_gap_signals,
    classify_fit_band,
    compute_deterministic_score,
    compute_embedding_score,
    compute_skill_seed_score,
    compute_vector_similarity,
)


class AmbiguousEmbedding:
    def __init__(self, *values: float) -> None:
        self.values = list(values)

    def __iter__(self):
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __bool__(self) -> bool:
        raise ValueError("The truth value of an array with more than one element is ambiguous.")


def test_compute_embedding_score() -> None:
    score = compute_embedding_score(
        ["python", "fastapi", "postgresql"],
        ["python", "django", "postgresql"],
    )

    assert score == 0.5


def test_compute_skill_seed_score_uses_full_skill_inventory() -> None:
    score = compute_skill_seed_score(
        candidate_core_skills=["python"],
        candidate_full_skills=["python", "django", "postgresql"],
        vacancy_skills=["python", "postgresql"],
    )

    assert score > 0.65


def test_compute_deterministic_score() -> None:
    score, breakdown = compute_deterministic_score(
        candidate_core_skills=["python", "fastapi"],
        candidate_full_skills=["python", "fastapi", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
        candidate_target_role="Senior Python Backend Developer",
        vacancy_role_title="Senior Python Engineer",
        candidate_work_format="remote",
        vacancy_work_format="remote",
        candidate_country_code="PL",
        candidate_city="Warsaw",
        candidate_english_level="C1",
        candidate_preferred_domains=["saas"],
        vacancy_countries_allowed=["PL"],
        vacancy_office_city=None,
        vacancy_required_english_level="B2",
        vacancy_project_description="B2B SaaS platform for developer analytics.",
    )

    assert score > 0.7
    assert breakdown["core_skill_overlap_ratio"] == 0.5
    assert breakdown["full_skill_overlap_ratio"] == 1.0
    assert breakdown["role_fit"] > 0.0
    assert breakdown["english_fit"] == 1.0
    assert breakdown["domain_fit"] > 0.0
    assert breakdown["process_fit"] == 0.5


def test_compute_deterministic_score_supports_multiple_candidate_work_formats() -> None:
    score, breakdown = compute_deterministic_score(
        candidate_core_skills=["python", "fastapi"],
        candidate_full_skills=["python", "fastapi", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
        candidate_target_role="Senior Python Backend Developer",
        vacancy_role_title="Senior Python Engineer",
        candidate_work_format=None,
        candidate_work_formats_json=["remote", "hybrid"],
        vacancy_work_format="hybrid",
        candidate_country_code="PL",
        candidate_city="Warsaw",
        candidate_english_level="C1",
        candidate_preferred_domains=["saas"],
        vacancy_countries_allowed=["PL"],
        vacancy_office_city="Warsaw",
        vacancy_required_english_level="B2",
        vacancy_project_description="B2B SaaS platform for developer analytics.",
    )

    assert score > 0.7
    assert breakdown["work_format_fit"] == 1.0


def test_compute_deterministic_score_rewards_cleaner_process() -> None:
    paid_score, paid_breakdown = compute_deterministic_score(
        candidate_core_skills=["python"],
        candidate_full_skills=["python", "django", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
        candidate_target_role="Senior Python Backend Developer",
        vacancy_role_title="Senior Python Engineer",
        candidate_work_format="remote",
        vacancy_work_format="remote",
        candidate_country_code="PL",
        candidate_city="Warsaw",
        candidate_english_level="C1",
        candidate_preferred_domains=["saas"],
        vacancy_countries_allowed=["PL"],
        vacancy_office_city=None,
        vacancy_required_english_level="B2",
        vacancy_project_description="B2B SaaS platform for developer analytics.",
        candidate_show_take_home_task_roles=True,
        candidate_show_live_coding_roles=True,
        vacancy_has_take_home_task=True,
        vacancy_take_home_paid=True,
        vacancy_has_live_coding=False,
        vacancy_hiring_stages=["recruiter_screen", "technical_interview"],
    )
    unpaid_score, unpaid_breakdown = compute_deterministic_score(
        candidate_core_skills=["python"],
        candidate_full_skills=["python", "django", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
        candidate_target_role="Senior Python Backend Developer",
        vacancy_role_title="Senior Python Engineer",
        candidate_work_format="remote",
        vacancy_work_format="remote",
        candidate_country_code="PL",
        candidate_city="Warsaw",
        candidate_english_level="C1",
        candidate_preferred_domains=["saas"],
        vacancy_countries_allowed=["PL"],
        vacancy_office_city=None,
        vacancy_required_english_level="B2",
        vacancy_project_description="B2B SaaS platform for developer analytics.",
        candidate_show_take_home_task_roles=True,
        candidate_show_live_coding_roles=True,
        vacancy_has_take_home_task=True,
        vacancy_take_home_paid=False,
        vacancy_has_live_coding=True,
        vacancy_hiring_stages=["recruiter_screen", "technical_interview", "live_coding", "final"],
    )

    assert paid_score > unpaid_score
    assert paid_breakdown["process_fit"] > unpaid_breakdown["process_fit"]


def test_compute_deterministic_score_uses_saved_feedback_categories() -> None:
    aligned_score, aligned_breakdown = compute_deterministic_score(
        candidate_core_skills=["python"],
        candidate_full_skills=["python", "django", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
        candidate_target_role="Senior Python Backend Developer",
        vacancy_role_title="Senior Python Engineer",
        candidate_work_format="remote",
        vacancy_work_format="remote",
        candidate_country_code="PL",
        candidate_city="Warsaw",
        candidate_english_level="C1",
        candidate_preferred_domains=["saas"],
        vacancy_countries_allowed=["PL"],
        vacancy_office_city=None,
        vacancy_required_english_level="B2",
        vacancy_project_description="B2B SaaS platform for developer analytics.",
        candidate_show_take_home_task_roles=True,
        candidate_show_live_coding_roles=True,
        vacancy_has_take_home_task=False,
        vacancy_take_home_paid=None,
        vacancy_has_live_coding=False,
        vacancy_hiring_stages=["recruiter_screen", "technical_interview"],
        candidate_salary_min=5000,
        candidate_salary_max=5500,
        vacancy_budget_min=6500,
        vacancy_budget_max=7500,
        candidate_feedback_categories=["process", "compensation"],
    )
    mismatch_score, mismatch_breakdown = compute_deterministic_score(
        candidate_core_skills=["python"],
        candidate_full_skills=["python", "django", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
        candidate_target_role="Senior Python Backend Developer",
        vacancy_role_title="Senior Python Engineer",
        candidate_work_format="remote",
        vacancy_work_format="remote",
        candidate_country_code="PL",
        candidate_city="Warsaw",
        candidate_english_level="C1",
        candidate_preferred_domains=["saas"],
        vacancy_countries_allowed=["PL"],
        vacancy_office_city=None,
        vacancy_required_english_level="B2",
        vacancy_project_description="B2B SaaS platform for developer analytics.",
        candidate_show_take_home_task_roles=True,
        candidate_show_live_coding_roles=True,
        vacancy_has_take_home_task=True,
        vacancy_take_home_paid=False,
        vacancy_has_live_coding=True,
        vacancy_hiring_stages=["recruiter_screen", "technical_interview", "live_coding", "final"],
        candidate_salary_min=5000,
        candidate_salary_max=5500,
        vacancy_budget_min=5000,
        vacancy_budget_max=5600,
        candidate_feedback_categories=["process", "compensation"],
    )

    assert aligned_score > mismatch_score
    assert aligned_breakdown["feedback_fit"] > mismatch_breakdown["feedback_fit"]
    assert aligned_breakdown["feedback_categories"] == ["process", "compensation"]


def test_classify_fit_band_and_gap_signals() -> None:
    fit_band = classify_fit_band(
        deterministic_score=0.66,
        llm_fit_score=0.68,
        score_breakdown={
            "core_skill_overlap_ratio": 0.5,
            "full_skill_overlap_ratio": 0.55,
            "role_fit": 0.35,
            "experience_score": 0.45,
            "domain_fit": 0.2,
            "process_fit": 0.6,
        },
    )

    gaps = build_gap_signals(
        score_breakdown={
            "core_skill_overlap_ratio": 0.5,
            "role_fit": 0.35,
            "experience_score": 0.45,
            "domain_fit": 0.2,
            "process_fit": 0.6,
        }
    )

    assert fit_band == "medium"
    assert gaps == [
        "Core stack overlap is partial.",
        "Role alignment is not exact.",
        "Experience level is closer to the lower bound of the role.",
    ]


def test_build_gap_signals_prioritizes_feedback_themes() -> None:
    gaps = build_gap_signals(
        score_breakdown={
            "core_skill_overlap_ratio": 0.75,
            "full_skill_overlap_ratio": 0.8,
            "role_fit": 0.7,
            "experience_score": 0.75,
            "domain_fit": 0.7,
            "process_fit": 0.45,
            "feedback_categories": ["process"],
        }
    )

    assert gaps[0] == "This role still misses saved hiring-process preferences."


def test_compute_vector_similarity() -> None:
    score = compute_vector_similarity(
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
    )

    assert score is not None
    assert score > 0.9


def test_compute_vector_similarity_handles_embeddings_without_bool_support() -> None:
    score = compute_vector_similarity(
        AmbiguousEmbedding(1.0, 0.0, 0.0),
        AmbiguousEmbedding(0.9, 0.1, 0.0),
    )

    assert score is not None
    assert score > 0.9
