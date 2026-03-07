from types import SimpleNamespace

from src.evaluation.scoring import evaluate_candidate


def test_evaluate_candidate_returns_advance_recommendation() -> None:
    vacancy = SimpleNamespace(primary_tech_stack_json=["python", "postgresql"])
    result = evaluate_candidate(
        candidate_summary={"skills": ["python", "postgresql"], "years_experience": 6},
        vacancy=vacancy,
        answer_texts=["A1", "A2", "A3", "A4", "A5"],
    )

    assert result["recommendation"] == "advance"
    assert result["final_score"] >= 0.65


def test_evaluate_candidate_returns_reject_for_weak_case() -> None:
    vacancy = SimpleNamespace(primary_tech_stack_json=["java", "spring"])
    result = evaluate_candidate(
        candidate_summary={"skills": ["python"], "years_experience": 1},
        vacancy=vacancy,
        answer_texts=["A1"],
    )

    assert result["recommendation"] == "reject"
