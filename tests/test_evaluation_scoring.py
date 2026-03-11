from __future__ import annotations

from types import SimpleNamespace

from src.evaluation.scoring import evaluate_candidate
from src.llm.service import LLMResult, evaluate_candidate_with_llm


def _candidate_summary() -> dict:
    return {
        "headline": "a senior full-stack engineer with deep JavaScript experience",
        "years_experience": 10,
        "skills": ["node.js", "typescript", "postgresql", "graphql", "redis"],
    }


def _vacancy():
    return SimpleNamespace(
        role_title="Node.js Developer",
        primary_tech_stack_json=["node.js", "typescript", "postgresql", "redis"],
    )


def _answers() -> list[str]:
    return [
        (
            "I designed the transaction builder as a rule-driven pipeline with deterministic validation, "
            "cached active rules, RabbitMQ, and ELK for monitoring."
        ),
        (
            "I would separate ingestion from repricing and keep the pricing engine reading the latest trusted "
            "snapshot from Redis so delayed feeds do not overwrite better data."
        ),
        "I built the service to stay stateless and horizontally scalable under heavy transaction volume.",
        "We used async workers and clear source-priority rules to keep the system stable.",
    ]


def test_baseline_interview_summary_is_not_a_transcript_dump() -> None:
    result = evaluate_candidate(
        candidate_summary=_candidate_summary(),
        vacancy=_vacancy(),
        answer_texts=_answers(),
    )

    summary = result["interview_summary"]

    assert "\n\n" in summary
    assert summary.startswith("The candidate comes across")
    assert "Overall," in summary
    assert "I designed the transaction builder" not in summary


def test_llm_interview_summary_preserves_paragraphs(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.llm.service._client.parse",
        lambda **_kwargs: LLMResult(
            payload={
                "final_score": 0.81,
                "strengths": ["Good backend fit."],
                "risks": ["Some answers stayed high-level."],
                "recommendation": "advance",
                "interview_summary": (
                    "The candidate comes across as a strong backend engineer. "
                    "They explained their work clearly.\n\n"
                    "The answers were concrete enough overall. "
                    "The fit for this role looks plausible."
                ),
            },
            model_name="fake-model",
            prompt_version="test",
        ),
    )

    result = evaluate_candidate_with_llm(_candidate_summary(), _vacancy(), _answers())

    assert "\n\n" in result.payload["interview_summary"]
    assert result.payload["interview_summary"].count("\n\n") == 1


def test_llm_transcript_dump_is_replaced_with_recruiter_style_summary(monkeypatch) -> None:
    transcript_dump = " ".join(_answers())

    monkeypatch.setattr(
        "src.llm.service._client.parse",
        lambda **_kwargs: LLMResult(
            payload={
                "final_score": 0.4,
                "strengths": ["Candidate has stated prior relevant experience."],
                "risks": ["Core stack overlap is limited."],
                "recommendation": "reject",
                "interview_summary": transcript_dump,
            },
            model_name="fake-model",
            prompt_version="test",
        ),
    )

    result = evaluate_candidate_with_llm(_candidate_summary(), _vacancy(), _answers())

    assert result.payload["interview_summary"] != transcript_dump
    assert "\n\n" in result.payload["interview_summary"]
    assert result.payload["interview_summary"].startswith("The candidate comes across")
