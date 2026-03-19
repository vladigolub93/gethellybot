from scripts.replay_question_utterances import (
    classify_payload_delta,
    evaluate_prompt_answer_pair,
    infer_prompt_context,
)
from src.candidate_profile.question_prompts import question_prompt as candidate_question_prompt
from src.vacancy.question_prompts import question_prompt as vacancy_question_prompt
from src.vacancy.question_prompts import follow_up_prompt as vacancy_follow_up_prompt


def test_infer_candidate_prompt_context() -> None:
    context = infer_prompt_context(candidate_question_prompt("english_level", work_formats=["remote"]))

    assert context == ("candidate", "english_level")


def test_infer_manager_prompt_context() -> None:
    context = infer_prompt_context(
        vacancy_follow_up_prompt("take_home_paid", work_format="remote", has_take_home_task=True)
    )

    assert context == ("manager", "take_home_paid")


def test_classify_payload_delta_recovered() -> None:
    assert classify_payload_delta(baseline_payload={}, enriched_payload={"english_level": "b2"}) == "recovered"


def test_evaluate_prompt_answer_pair_recovers_candidate_domains() -> None:
    finding = evaluate_prompt_answer_pair(
        candidate_question_prompt("preferred_domains", work_formats=["remote", "hybrid", "office"]),
        "нет",
    )

    assert finding is not None
    assert finding.role == "candidate"
    assert finding.question_key == "preferred_domains"
    assert finding.classification == "recovered"
    assert finding.enriched_payload["preferred_domains_json"] == ["any"]


def test_evaluate_prompt_answer_pair_improves_manager_assessment() -> None:
    finding = evaluate_prompt_answer_pair(
        vacancy_question_prompt("assessment", work_format="remote", has_take_home_task=True),
        "только тестовая таска",
    )

    assert finding is not None
    assert finding.role == "manager"
    assert finding.question_key == "assessment"
    assert finding.classification in {"recovered", "improved"}
    assert finding.enriched_payload["has_take_home_task"] is True
    assert finding.enriched_payload["has_live_coding"] is False
