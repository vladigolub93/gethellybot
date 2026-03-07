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
