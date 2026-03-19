import pytest

from src.candidate_profile.questions import enrich_candidate_question_payload_for_current_question
from src.vacancy.questions import enrich_vacancy_clarification_payload_for_current_question
from tests.question_utterance_corpus_data import CANDIDATE_UTTERANCE_CASES, MANAGER_UTTERANCE_CASES


@pytest.mark.parametrize(
    ("question_key", "text", "expected"),
    CANDIDATE_UTTERANCE_CASES,
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
    MANAGER_UTTERANCE_CASES,
)
def test_manager_current_question_utterance_corpus(question_key: str, text: str, expected: dict) -> None:
    parsed = enrich_vacancy_clarification_payload_for_current_question(
        parsed={},
        text=text,
        current_question_key=question_key,
    )

    assert parsed == expected


def test_candidate_current_question_falls_back_when_llm_payload_is_semantically_empty() -> None:
    parsed = enrich_candidate_question_payload_for_current_question(
        parsed={"preferred_domains_json": []},
        text="нет",
        current_question_key="preferred_domains",
    )

    assert parsed == {"preferred_domains_json": ["any"]}


def test_manager_current_question_falls_back_when_llm_payload_is_semantically_empty() -> None:
    parsed = enrich_vacancy_clarification_payload_for_current_question(
        parsed={"countries_allowed_json": []},
        text="Ukraine, Poland",
        current_question_key="countries",
    )

    assert parsed == {"countries_allowed_json": ["UA", "PL"]}
