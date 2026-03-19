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
