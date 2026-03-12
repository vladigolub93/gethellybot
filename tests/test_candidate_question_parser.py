from src.candidate_profile.question_parser import parse_candidate_questions


def test_parse_candidate_questions_combined_text() -> None:
    parsed = parse_candidate_questions(
        "Salary: $5000 per month. Location: Warsaw, Poland. Prefer remote work."
    )

    assert parsed["salary_min"] == 5000
    assert parsed["salary_max"] == 5000
    assert parsed["salary_currency"] == "USD"
    assert parsed["salary_period"] == "month"
    assert parsed["location_text"] == "Warsaw, Poland"
    assert parsed["city"] == "Warsaw"
    assert parsed["country_code"] == "PL"
    assert parsed["work_format"] == "remote"


def test_parse_candidate_questions_partial_text() -> None:
    parsed = parse_candidate_questions("Currently in Berlin, Germany and open to hybrid.")

    assert parsed["location_text"] == "Berlin, Germany"
    assert parsed["work_format"] == "hybrid"


def test_parse_candidate_questions_extracts_matching_preferences() -> None:
    parsed = parse_candidate_questions(
        "English: C1. Prefer fintech and SaaS. Show take-home roles, but no live coding."
    )

    assert parsed["english_level"] == "c1"
    assert parsed["preferred_domains_json"] == ["fintech", "saas"]
    assert parsed["show_take_home_task_roles"] is True
    assert parsed["show_live_coding_roles"] is False


def test_parse_candidate_questions_ru_ua_matching_preferences() -> None:
    parsed = parse_candidate_questions(
        "Зарплата: 4500-5000 USD в месяц. Живу в Киев, Украина и предпочитаю удаленно. "
        "Английский: B2. Предпочитаю фінтех и SaaS. Тестовое задание ок, но без лайвкодинга."
    )

    assert parsed["salary_min"] == 4500
    assert parsed["salary_max"] == 5000
    assert parsed["salary_currency"] == "USD"
    assert parsed["salary_period"] == "month"
    assert parsed["country_code"] == "UA"
    assert parsed["work_format"] == "remote"
    assert parsed["english_level"] == "b2"
    assert parsed["preferred_domains_json"] == ["fintech", "saas"]
    assert parsed["show_take_home_task_roles"] is True
    assert parsed["show_live_coding_roles"] is False
