import pytest

from src.candidate_profile.questions import enrich_candidate_question_payload_for_current_question
from src.vacancy.questions import enrich_vacancy_clarification_payload_for_current_question


@pytest.mark.parametrize(
    ("question_key", "text", "expected"),
    [
        ("work_format", "all formats", {"work_formats_json": ["remote", "hybrid", "office"], "work_format": None}),
        ("work_format", "все подходит", {"work_formats_json": ["remote", "hybrid", "office"], "work_format": None}),
        ("work_format", "все форматы", {"work_formats_json": ["remote", "hybrid", "office"], "work_format": None}),
        ("english_level", "выше среднего", {"english_level": "b2"}),
        ("english_level", "б2", {"english_level": "b2"}),
        ("preferred_domains", "нет", {"preferred_domains_json": ["any"]}),
        ("preferred_domains", "мне все равно", {"preferred_domains_json": ["any"]}),
        ("preferred_domains", "мне все рано", {"preferred_domains_json": ["any"]}),
        (
            "assessment_preferences",
            "не хочу",
            {"show_take_home_task_roles": False, "show_live_coding_roles": False},
        ),
        (
            "assessment_preferences",
            "я же сказал что только тестовая таска ок",
            {"show_take_home_task_roles": True, "show_live_coding_roles": False},
        ),
    ],
)
def test_candidate_current_question_utterance_corpus(question_key: str, text: str, expected: dict) -> None:
    parsed = enrich_candidate_question_payload_for_current_question(
        parsed={},
        text=text,
        current_question_key=question_key,
    )

    assert parsed == expected


@pytest.mark.parametrize(
    ("question_key", "text", "expected"),
    [
        ("budget", "7000-9000 usd per month", {"budget_min": 7000, "budget_max": 9000, "budget_currency": "USD", "budget_period": "month"}),
        ("work_format", "удаленно", {"work_format": "remote"}),
        ("office_city", "Warsaw", {"office_city": "Warsaw"}),
        ("english_level", "с1", {"required_english_level": "c1"}),
        ("assessment", "оба", {"has_take_home_task": True, "has_live_coding": True}),
        ("assessment", "только тестовая таска", {"has_take_home_task": True, "has_live_coding": False}),
        ("take_home_paid", "оплачиваемое", {"take_home_paid": True}),
        ("take_home_paid", "неоплачиваемое", {"take_home_paid": False}),
        ("team_size", "6", {"team_size": 6}),
        ("project_description", "B2B payments platform for SMB merchants.", {"project_description": "B2B payments platform for SMB merchants."}),
        ("primary_tech_stack", "Python, FastAPI, PostgreSQL", {"primary_tech_stack_json": ["python", "fastapi", "postgresql"]}),
    ],
)
def test_manager_current_question_utterance_corpus(question_key: str, text: str, expected: dict) -> None:
    parsed = enrich_vacancy_clarification_payload_for_current_question(
        parsed={},
        text=text,
        current_question_key=question_key,
    )

    assert parsed == expected
