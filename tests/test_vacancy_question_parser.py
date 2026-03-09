from src.vacancy.question_parser import parse_vacancy_clarifications


def test_parse_vacancy_clarifications_combined_text() -> None:
    parsed = parse_vacancy_clarifications(
        "Budget: $7000-$9000 per month. Countries: Poland and Germany. "
        "Remote. Team size: 6. Project: B2B payments platform. "
        "Primary stack: Python, FastAPI, PostgreSQL."
    )

    assert parsed["budget_min"] == 7000
    assert parsed["budget_max"] == 9000
    assert parsed["budget_currency"] == "USD"
    assert parsed["budget_period"] == "month"
    assert parsed["countries_allowed_json"] == ["PL", "DE"]
    assert parsed["work_format"] == "remote"
    assert parsed["team_size"] == 6
    assert "payments platform" in parsed["project_description"]
    assert parsed["primary_tech_stack_json"][:3] == ["python", "fastapi", "postgresql"]


def test_parse_vacancy_clarifications_accepts_project_link() -> None:
    parsed = parse_vacancy_clarifications("https://repriced.ai")

    assert parsed["project_description"] == "https://repriced.ai"
