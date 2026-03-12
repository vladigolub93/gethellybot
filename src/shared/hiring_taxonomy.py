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
    ("a1", ("a1", "beginner english", "початковий", "начальный")),
    (
        "a2",
        ("a2", "elementary", "pre intermediate", "pre-intermediate", "basic english", "базовый", "базовий"),
    ),
    (
        "b1",
        (
            "b1",
            "intermediate",
            "conversational english",
            "средний",
            "середній",
            "розмовний",
            "разговорный",
        ),
    ),
    (
        "b2",
        (
            "b2",
            "upper intermediate",
            "upper-intermediate",
            "вище середнього",
            "выше среднего",
        ),
    ),
    (
        "c1",
        (
            "c1",
            "advanced",
            "fluent",
            "professional working proficiency",
            "advanced english",
            "свободный",
            "вільний",
            "просунутий",
            "продвинутый",
        ),
    ),
    (
        "c2",
        ("c2", "proficient", "full professional proficiency", "near native", "майже як носій"),
    ),
    ("native", ("native", "native english", "mother tongue", "носитель", "носій", "рідна", "родной")),
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
    ("fintech", ("fintech", "finance", "payments", "banking", "финтех", "фінтех", "платежи", "платежі")),
    (
        "healthtech",
        ("healthtech", "health tech", "healthcare", "medtech", "medical", "медтех", "health care"),
    ),
    ("edtech", ("edtech", "education", "education tech", "едтех", "освіта", "образование")),
    ("ecommerce", ("ecommerce", "e-commerce", "retail", "ecommerce platform", "е-коммерция", "e-commerce")),
    ("saas", ("saas", "b2b saas", "software as a service", "саас")),
    (
        "ai_ml",
        (
            "ai",
            "ml",
            "machine learning",
            "artificial intelligence",
            "llm",
            "штучний інтелект",
            "искусственный интеллект",
            "машинное обучение",
            "машинне навчання",
        ),
    ),
    ("gaming", ("gaming", "games", "gamedev", "game dev", "геймдев", "игры", "ігри")),
    ("devtools", ("devtools", "developer tools", "developer infrastructure", "dev tools")),
    ("cybersecurity", ("cybersecurity", "security", "infosec", "кібербезпека", "кибербезопасность")),
    ("web3", ("web3", "crypto", "blockchain", "крипто", "блокчейн")),
    ("logistics", ("logistics", "supply chain", "transport", "логистика", "логістика")),
    ("marketplace", ("marketplace", "classifieds", "маркетплейс")),
    ("adtech", ("adtech", "advertising", "реклама", "advertisement tech")),
    ("martech", ("martech", "marketing tech", "crm", "маркетинг тех")),
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
    (
        "recruiter_screen",
        (
            "recruiter screen",
            "recruiter call",
            "hr screen",
            "hr call",
            "intro call",
            "скрин с рекрутером",
            "звонок с рекрутером",
            "дзвінок з рекрутером",
            "скрин з рекрутером",
        ),
    ),
    (
        "manager_screen",
        (
            "manager screen",
            "manager call",
            "hiring manager call",
            "звонок с менеджером",
            "інтерв'ю з менеджером",
            "скрин с менеджером",
        ),
    ),
    (
        "technical_interview",
        ("technical interview", "tech interview", "техническое интервью", "тех интервью", "технічне інтерв'ю"),
    ),
    (
        "system_design",
        ("system design", "architecture interview", "design interview", "систем дизайн", "дизайн системы", "системний дизайн"),
    ),
    (
        "live_coding",
        (
            "live coding",
            "live-coding",
            "coding interview",
            "pair programming",
            "лайвкодинг",
            "лайв кодинг",
            "парное программирование",
            "парне програмування",
        ),
    ),
    (
        "take_home",
        (
            "take home",
            "take-home",
            "test task",
            "home assignment",
            "тестовое задание",
            "тестове завдання",
            "домашнее задание",
            "домашнє завдання",
        ),
    ),
    ("team_fit", ("team fit", "culture fit", "team interview", "командное интервью", "командна співбесіда")),
    ("final", ("final", "final interview", "final round", "финальный этап", "финальное интервью", "фінальний етап", "фінальне інтерв'ю")),
    ("founder_call", ("founder call", "ceo call", "звонок с фаундером", "дзвінок з фаундером")),
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
            if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", normalized):
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
