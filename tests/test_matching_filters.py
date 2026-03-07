from types import SimpleNamespace

from src.matching.filters import evaluate_hard_filters


def test_evaluate_hard_filters_returns_reason_codes() -> None:
    candidate = SimpleNamespace(
        country_code="UA",
        work_format="remote",
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
