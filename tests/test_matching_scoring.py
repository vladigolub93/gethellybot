from src.matching.scoring import (
    compute_deterministic_score,
    compute_embedding_score,
    compute_vector_similarity,
)


def test_compute_embedding_score() -> None:
    score = compute_embedding_score(
        ["python", "fastapi", "postgresql"],
        ["python", "django", "postgresql"],
    )

    assert score == 0.5


def test_compute_deterministic_score() -> None:
    score, breakdown = compute_deterministic_score(
        candidate_skills=["python", "fastapi", "postgresql"],
        vacancy_skills=["python", "postgresql"],
        candidate_years_experience=6,
        vacancy_seniority="senior",
        candidate_seniority="senior",
    )

    assert score > 0.8
    assert breakdown["skill_overlap_ratio"] == 1.0


def test_compute_vector_similarity() -> None:
    score = compute_vector_similarity(
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
    )

    assert score is not None
    assert score > 0.9
