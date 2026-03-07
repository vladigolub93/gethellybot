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


def build_vacancy_summary(source_text: str, source_type: str) -> tuple[dict, dict]:
    normalized = _normalize_text(source_text)
    tech_stack = detect_primary_stack(normalized)
    summary = {
        "status": "draft",
        "source_type": source_type,
        "role_title": detect_role_title(normalized),
        "seniority_normalized": detect_seniority(normalized),
        "primary_tech_stack": tech_stack,
        "project_description_excerpt": normalized[:1200],
    }
    inconsistency_json = detect_inconsistencies(normalized, tech_stack)
    return summary, inconsistency_json
