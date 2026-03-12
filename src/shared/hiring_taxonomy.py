from __future__ import annotations

import re
from typing import Iterable


ENGLISH_LEVEL_ORDER = {
    "a1": 1,
    "a2": 2,
    "b1": 3,
    "b2": 4,
    "c1": 5,
    "c2": 6,
    "native": 7,
}

_ENGLISH_LEVEL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("a1", ("a1", "beginner english")),
    ("a2", ("a2", "elementary", "pre intermediate", "pre-intermediate", "basic english")),
    ("b1", ("b1", "intermediate", "conversational english")),
    ("b2", ("b2", "upper intermediate", "upper-intermediate")),
    ("c1", ("c1", "advanced", "fluent", "professional working proficiency")),
    ("c2", ("c2", "proficient", "full professional proficiency")),
    ("native", ("native", "native english", "mother tongue")),
)

ENGLISH_LEVEL_DISPLAY = {
    "a1": "A1",
    "a2": "A2",
    "b1": "B1",
    "b2": "B2",
    "c1": "C1",
    "c2": "C2",
    "native": "Native",
}

DOMAIN_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fintech", ("fintech", "finance", "payments", "banking")),
    ("healthtech", ("healthtech", "health tech", "healthcare", "medtech", "medical")),
    ("edtech", ("edtech", "education", "education tech")),
    ("ecommerce", ("ecommerce", "e-commerce", "retail")),
    ("saas", ("saas", "b2b saas", "software as a service")),
    ("ai_ml", ("ai", "ml", "machine learning", "artificial intelligence", "llm")),
    ("gaming", ("gaming", "games", "gamedev", "game dev")),
    ("devtools", ("devtools", "developer tools", "developer infrastructure")),
    ("cybersecurity", ("cybersecurity", "security", "infosec")),
    ("web3", ("web3", "crypto", "blockchain")),
    ("logistics", ("logistics", "supply chain", "transport")),
    ("marketplace", ("marketplace", "classifieds")),
    ("adtech", ("adtech", "advertising")),
    ("martech", ("martech", "marketing tech", "crm")),
)

DOMAIN_DISPLAY = {
    "any": "Any domain",
    "fintech": "Fintech",
    "healthtech": "Healthtech",
    "edtech": "Edtech",
    "ecommerce": "E-commerce",
    "saas": "SaaS",
    "ai_ml": "AI/ML",
    "gaming": "Gaming",
    "devtools": "Devtools",
    "cybersecurity": "Cybersecurity",
    "web3": "Web3",
    "logistics": "Logistics",
    "marketplace": "Marketplace",
    "adtech": "Adtech",
    "martech": "Martech",
}

HIRING_STAGE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("recruiter_screen", ("recruiter screen", "recruiter call", "hr screen", "hr call", "intro call")),
    ("manager_screen", ("manager screen", "manager call", "hiring manager call")),
    ("technical_interview", ("technical interview", "tech interview")),
    ("system_design", ("system design", "architecture interview", "design interview")),
    ("live_coding", ("live coding", "live-coding", "coding interview", "pair programming")),
    ("take_home", ("take home", "take-home", "test task", "home assignment")),
    ("team_fit", ("team fit", "culture fit", "team interview")),
    ("final", ("final", "final interview", "final round")),
    ("founder_call", ("founder call", "ceo call")),
)

HIRING_STAGE_DISPLAY = {
    "recruiter_screen": "Recruiter screen",
    "manager_screen": "Manager screen",
    "technical_interview": "Technical interview",
    "system_design": "System design",
    "live_coding": "Live coding",
    "take_home": "Take-home task",
    "team_fit": "Team fit",
    "final": "Final interview",
    "founder_call": "Founder call",
}


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_english_level(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    for canonical, aliases in _ENGLISH_LEVEL_ALIASES:
        if normalized == canonical or normalized in aliases:
            return canonical
    return None


def display_english_level(value: str | None) -> str | None:
    normalized = normalize_english_level(value)
    if not normalized:
        return None
    return ENGLISH_LEVEL_DISPLAY.get(normalized, normalized.upper())


def compare_english_levels(candidate_level: str | None, required_level: str | None) -> int | None:
    normalized_candidate = normalize_english_level(candidate_level)
    normalized_required = normalize_english_level(required_level)
    if not normalized_candidate or not normalized_required:
        return None
    return ENGLISH_LEVEL_ORDER[normalized_candidate] - ENGLISH_LEVEL_ORDER[normalized_required]


def _collect_matches(text: str | None, groups: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    found: list[str] = []
    for canonical, aliases in groups:
        for alias in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
                found.append(canonical)
                break
    return found


def extract_domains(text: str | None, *, extra_values: Iterable[str] | None = None) -> list[str]:
    found = _collect_matches(text, DOMAIN_ALIASES)
    seen = set(found)
    for extra in extra_values or []:
        normalized = _normalize_text(extra)
        if normalized == "any" and normalized not in seen:
            found.append(normalized)
            seen.add(normalized)
        if normalized in DOMAIN_DISPLAY and normalized not in seen:
            found.append(normalized)
            seen.add(normalized)
    return found


def display_domains(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    seen = set()
    for value in values or []:
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(DOMAIN_DISPLAY.get(normalized, normalized.replace("_", " ").title()))
    return result


def extract_hiring_stages(text: str | None, *, extra_values: Iterable[str] | None = None) -> list[str]:
    found = _collect_matches(text, HIRING_STAGE_ALIASES)
    seen = set(found)
    for extra in extra_values or []:
        normalized = _normalize_text(extra)
        if normalized in HIRING_STAGE_DISPLAY and normalized not in seen:
            found.append(normalized)
            seen.add(normalized)
    return found


def display_hiring_stages(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    seen = set()
    for value in values or []:
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(HIRING_STAGE_DISPLAY.get(normalized, normalized.replace("_", " ").title()))
    return result
