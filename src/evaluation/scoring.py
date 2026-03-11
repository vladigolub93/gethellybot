from __future__ import annotations

import re
from typing import Iterable


_TECH_TERM_ALIASES = (
    "node.js",
    "typescript",
    "javascript",
    "postgresql",
    "mysql",
    "mongodb",
    "graphql",
    "redis",
    "rabbitmq",
    "kafka",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "terraform",
    "react",
    "next.js",
    "nestjs",
    "express.js",
    "elk",
)


def _normalize_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _collect_answer_texts(answer_texts: Iterable[str]) -> list[str]:
    return [_normalize_whitespace(text) for text in answer_texts if _normalize_whitespace(text)]


def _extract_detected_terms(text: str, candidate_summary: dict, vacancy) -> list[str]:
    detected: list[str] = []
    haystack = f" {text.lower()} "
    candidate_skills = [str(skill).strip().lower() for skill in (candidate_summary.get("skills") or [])]
    vacancy_skills = [str(skill).strip().lower() for skill in (getattr(vacancy, "primary_tech_stack_json", None) or [])]

    for term in list(dict.fromkeys(candidate_skills + vacancy_skills + list(_TECH_TERM_ALIASES))):
        if not term:
            continue
        if f" {term} " in haystack or term in haystack:
            detected.append(term)
        if len(detected) >= 4:
            break
    return detected


def _extract_detected_topics(text: str) -> list[str]:
    keyword_topics = [
        ("transaction", "transaction-heavy backend flows"),
        ("rule", "rule-driven processing"),
        ("pipeline", "pipeline design"),
        ("pricing", "repricing and pricing logic"),
        ("queue", "async queue-based processing"),
        ("rabbitmq", "async queue-based processing"),
        ("redis", "cache-backed data access"),
        ("monitor", "monitoring and observability"),
        ("elk", "monitoring and observability"),
        ("microservice", "microservice architecture"),
    ]
    lowered = text.lower()
    topics: list[str] = []
    for keyword, topic in keyword_topics:
        if keyword in lowered and topic not in topics:
            topics.append(topic)
        if len(topics) >= 3:
            break
    return topics


def _join_human(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _candidate_background(candidate_summary: dict) -> str:
    years = candidate_summary.get("years_experience")
    headline = _normalize_whitespace(candidate_summary.get("headline"))
    target_role = _normalize_whitespace(candidate_summary.get("target_role"))
    skills = [str(skill).strip() for skill in (candidate_summary.get("skills") or []) if str(skill).strip()]

    if headline:
        background = f"The candidate comes across as {headline}."
    elif target_role:
        background = f"The candidate comes across as a {target_role} candidate."
    elif years:
        background = f"The candidate comes across as an engineer with around {years} years of claimed experience."
    else:
        background = "The candidate comes across as an experienced software engineer."

    if years and "years" not in background.lower():
        background = background.rstrip(".") + f" They claim around {years} years of experience."

    if skills:
        background += f" Their profile is mainly oriented around {_join_human(skills[:4])}."

    return background


def _clarity_sentence(*, answer_count: int, detected_terms: list[str], detected_topics: list[str]) -> str:
    if detected_topics:
        return (
            f"They described {_join_human(detected_topics)} in the interview and their explanations were "
            f"{'fairly clear' if answer_count >= 4 else 'only partially developed'}."
        )
    if detected_terms:
        return (
            f"They referenced {_join_human(detected_terms[:3])} while explaining their work, and the answers were "
            f"{'reasonably clear' if answer_count >= 4 else 'somewhat brief'}."
        )
    return (
        "They answered the interview questions directly, although the explanations stayed fairly general."
        if answer_count >= 3
        else "They answered only part of the interview, so the picture is still incomplete."
    )


def _depth_sentence(*, answer_count: int, ownership_markers: int, detected_terms: list[str]) -> str:
    if ownership_markers >= 2 and answer_count >= 4:
        return "The answers were fairly concrete and showed credible ownership over implementation details."
    if ownership_markers >= 1:
        return "Some answers sounded experience-based, although not every point was backed by concrete ownership detail."
    if answer_count >= 4 and detected_terms:
        return (
            "The candidate discussed technical topics with some structure, but several answers stayed generic and light on personal ownership."
        )
    return "The interview did not strongly confirm technical depth or hands-on ownership."


def _fit_sentence(*, score: float, recommendation: str, vacancy_role: str | None) -> str:
    role_label = vacancy_role or "this role"
    if recommendation == "advance":
        return f"Overall, the interview suggests a plausible fit for {role_label}, although follow-up probing would still be useful."
    if score >= 0.45:
        return f"Overall, the candidate may be directionally relevant for {role_label}, but the interview did not confirm the fit strongly enough yet."
    return f"Overall, the current interview evidence does not yet support a strong recommendation for {role_label}."


def build_interview_summary(*, candidate_summary: dict, vacancy, answer_texts: list[str], score: float, recommendation: str) -> str:
    normalized_answers = _collect_answer_texts(answer_texts)
    joined_answers = " ".join(normalized_answers)
    answer_count = len(normalized_answers)
    detected_terms = _extract_detected_terms(joined_answers, candidate_summary, vacancy)
    detected_topics = _extract_detected_topics(joined_answers)
    ownership_markers = sum(
        1
        for answer in normalized_answers
        if re.search(r"\b(i built|i designed|i implemented|i owned|i led|we built|we implemented)\b", answer.lower())
    )

    vacancy_role = _normalize_whitespace(getattr(vacancy, "role_title", None))

    paragraph_one = " ".join(
        [
            _candidate_background(candidate_summary),
            _clarity_sentence(
                answer_count=answer_count,
                detected_terms=detected_terms,
                detected_topics=detected_topics,
            ),
            "The work was explained with enough structure to understand the main scope."
            if answer_count >= 4
            else "The explanation of the actual work stayed somewhat high-level.",
        ]
    ).strip()

    paragraph_two = " ".join(
        [
            _depth_sentence(
                answer_count=answer_count,
                ownership_markers=ownership_markers,
                detected_terms=detected_terms,
            ),
            (
                "Some responses sounded polished and generalized, which leaves a small risk of AI-assisted or rehearsed answering."
                if answer_count >= 3 and ownership_markers == 0
                else "There were at least some signals of genuine hands-on involvement in the described work."
            ),
            _fit_sentence(score=score, recommendation=recommendation, vacancy_role=vacancy_role),
        ]
    ).strip()

    return f"{paragraph_one}\n\n{paragraph_two}".strip()


def evaluate_candidate(*, candidate_summary: dict, vacancy, answer_texts: list[str]) -> dict:
    skills = {str(skill).strip().lower() for skill in (candidate_summary.get("skills") or []) if str(skill).strip()}
    vacancy_skills = {
        str(skill).strip().lower()
        for skill in (getattr(vacancy, "primary_tech_stack_json", None) or [])
        if str(skill).strip()
    }
    overlap_skills = sorted(skills & vacancy_skills)
    overlap = len(overlap_skills)
    required = len(vacancy_skills) or 1
    skill_ratio = overlap / required
    normalized_answers = _collect_answer_texts(answer_texts)
    answer_count = len(normalized_answers)
    answer_score = min(answer_count / 5.0, 1.0)
    ownership_markers = sum(
        1
        for answer in normalized_answers
        if re.search(r"\b(i built|i designed|i implemented|i owned|i led|we built|we implemented)\b", answer.lower())
    )
    ownership_bonus = min(ownership_markers / 3.0, 1.0)
    score = round((skill_ratio * 0.5) + (answer_score * 0.3) + (ownership_bonus * 0.2), 4)

    strengths = []
    risks = []
    if overlap_skills:
        strengths.append(f"Relevant stack overlap for this role, including {_join_human(overlap_skills[:3])}.")
    if candidate_summary.get("years_experience"):
        strengths.append("The profile indicates prior relevant engineering experience.")
    if answer_count >= 4:
        strengths.append("Interview coverage was broad enough to test multiple areas of the role.")

    if answer_count < 4:
        risks.append("Interview coverage was limited, so role fit is not fully validated yet.")
    if skill_ratio < 0.5:
        risks.append("Core stack overlap with the vacancy looks limited.")
    if ownership_markers == 0:
        risks.append("The answers did not clearly demonstrate personal ownership over implementation decisions.")

    recommendation = "advance" if score >= 0.65 else "reject"
    return {
        "final_score": score,
        "strengths": strengths,
        "risks": risks,
        "recommendation": recommendation,
        "interview_summary": build_interview_summary(
            candidate_summary=candidate_summary,
            vacancy=vacancy,
            answer_texts=normalized_answers,
            score=score,
            recommendation=recommendation,
        )[:1500],
    }
