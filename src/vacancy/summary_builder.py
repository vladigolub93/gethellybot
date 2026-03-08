from __future__ import annotations

from typing import Optional

from src.candidate_profile.summary_builder import KNOWN_SKILLS


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def detect_seniority(text: str) -> Optional[str]:
    lowered = text.lower()
    if "senior" in lowered or "lead" in lowered or "staff" in lowered:
        return "senior"
    if "middle" in lowered or "mid-level" in lowered or "mid level" in lowered:
        return "middle"
    if "junior" in lowered or "trainee" in lowered:
        return "junior"
    return None


def detect_role_title(text: str) -> Optional[str]:
    normalized = _normalize_text(text)
    for separator in (".", "\n", ","):
        head = normalized.split(separator, 1)[0].strip()
        if 3 <= len(head) <= 80:
            return head
    return normalized[:80].strip() or None


def detect_primary_stack(text: str) -> list[str]:
    lowered = _normalize_text(text).lower()
    found = []
    for skill in KNOWN_SKILLS:
        if skill in lowered:
            found.append(skill)
    return found[:8]


def detect_inconsistencies(text: str, tech_stack: list[str]) -> dict:
    issues = []
    backend_langs = [skill for skill in tech_stack if skill in {"python", "java", "javascript", "typescript"}]
    if len(backend_langs) >= 3:
        issues.append("Multiple primary backend languages detected; clarify actual core stack.")
    if "remote" in text.lower() and "office" in text.lower():
        issues.append("Remote and office requirements both appear; clarify intended work format.")
    return {"issues": issues}


def build_vacancy_approval_summary_text(
    *,
    role_title: str | None,
    seniority_normalized: str | None,
    primary_tech_stack: list[str],
    project_description_excerpt: str | None,
    source_text: str,
) -> str:
    role = (role_title or "software role").strip(" .,-")
    seniority = (seniority_normalized or "").strip()
    sentence_one = (
        f"This vacancy is for a {seniority} {role}."
        if seniority
        else f"This vacancy is for a {role}."
    )

    if primary_tech_stack:
        if len(primary_tech_stack) == 1:
            stack_part = primary_tech_stack[0]
        elif len(primary_tech_stack) == 2:
            stack_part = f"{primary_tech_stack[0]} and {primary_tech_stack[1]}"
        else:
            stack_part = ", ".join(primary_tech_stack[:4])
        sentence_two = f"The main stack includes {stack_part}."
    else:
        sentence_two = "The role focuses on the technologies and systems described in the job description."

    lowered = (project_description_excerpt or source_text or "").lower()
    if any(token in lowered for token in ("fintech", "payments", "bank", "trading")):
        sentence_three = "The work is related to fintech or payment-oriented systems."
    elif any(token in lowered for token in ("saas", "b2b", "crm", "platform")):
        sentence_three = "The work is related to a product or platform environment with business-facing software."
    elif project_description_excerpt:
        excerpt = project_description_excerpt.strip(" .")
        sentence_three = f"The role is focused on {excerpt[:180]}."
    else:
        sentence_three = "The role is focused on the product and delivery context described in the vacancy."

    return f"{sentence_one} {sentence_two} {sentence_three}"


def build_vacancy_summary(source_text: str, source_type: str) -> tuple[dict, dict]:
    normalized = _normalize_text(source_text)
    tech_stack = detect_primary_stack(normalized)
    role_title = detect_role_title(normalized)
    seniority = detect_seniority(normalized)
    project_excerpt = normalized[:1200]
    summary = {
        "status": "draft",
        "source_type": source_type,
        "role_title": role_title,
        "seniority_normalized": seniority,
        "primary_tech_stack": tech_stack,
        "project_description_excerpt": project_excerpt,
        "approval_summary_text": build_vacancy_approval_summary_text(
            role_title=role_title,
            seniority_normalized=seniority,
            primary_tech_stack=tech_stack,
            project_description_excerpt=project_excerpt,
            source_text=normalized,
        ),
    }
    inconsistency_json = detect_inconsistencies(normalized, tech_stack)
    return summary, inconsistency_json
