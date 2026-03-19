from types import SimpleNamespace

from src.matching.filters import evaluate_hard_filters


def test_evaluate_hard_filters_returns_reason_codes() -> None:
    candidate = SimpleNamespace(
        country_code="UA",
        work_format="remote",
        work_formats_json=["remote"],
        salary_min=7000,
        seniority_normalized="middle",
    )
    vacancy = SimpleNamespace(
        countries_allowed_json=["PL", "DE"],
        work_format="office",
        budget_max=5000,
        seniority_normalized="senior",
    )

    reasons = evaluate_hard_filters(candidate, vacancy)

    assert reasons == [
        "location_mismatch",
        "work_format_mismatch",
        "salary_above_budget",
        "seniority_mismatch",
    ]


def test_evaluate_hard_filters_allows_candidate_with_multiple_work_formats() -> None:
    candidate = SimpleNamespace(
        country_code="PL",
        work_format=None,
        work_formats_json=["remote", "hybrid"],
        salary_min=4000,
        seniority_normalized="senior",
    )
    vacancy = SimpleNamespace(
        countries_allowed_json=["PL"],
        work_format="hybrid",
        budget_max=5000,
        seniority_normalized="senior",
    )

    reasons = evaluate_hard_filters(candidate, vacancy)

    assert "work_format_mismatch" not in reasons
