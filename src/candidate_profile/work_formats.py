from __future__ import annotations

import re
from typing import Iterable, Sequence


WORK_FORMAT_ORDER = ("remote", "hybrid", "office")

_WORK_FORMAT_SYNONYMS = {
    "remote": ("remote", "удаленно", "удалённо", "віддалено", "дистанційно"),
    "hybrid": ("hybrid", "гибрид", "гібрид"),
    "office": ("office", "onsite", "on-site", "офис", "офіс", "онсайт"),
}

_ALL_FORMAT_PATTERNS = (
    r"\ball(?:\s+formats?)\b",
    r"\ball(?:\s+options?)\b",
    r"\bany(?:\s+formats?)\b",
    r"\bany of them\b",
    r"\ball of them\b",
    r"\b(?:все|всё|усі)\s+(?:форматы?|формати|варианты?|варіанти|подходит|подходят|підходить|підходять|ок)\b",
    r"\b(?:любой|любые|будь-який|будь-які)\s+формат(?:ы|и)?\b",
)

_SHORTHAND_ALL_VALUES = {
    "all",
    "any",
    "все",
    "всё",
    "все подходит",
    "всё подходит",
    "все форматы",
    "всё форматы",
    "все форматы подходят",
    "всё форматы подходят",
    "усі",
    "любой",
    "будь-який",
    "без разницы",
    "без різниці",
    "не важно",
    "неважно",
}


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def normalize_work_format(value: str | None) -> str | None:
    normalized = _normalize_text(value).lower()
    if normalized in {"remote", "hybrid", "office"}:
        return normalized
    if normalized in {"onsite", "on-site"}:
        return "office"
    return None


def normalize_work_formats(values: Iterable[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = normalize_work_format(value)
        if item is None or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return [value for value in WORK_FORMAT_ORDER if value in seen]


def build_work_formats_payload(formats: Sequence[str] | None) -> dict:
    normalized = normalize_work_formats(formats)
    if not normalized:
        return {}
    return {
        "work_formats_json": normalized,
        "work_format": normalized[0] if len(normalized) == 1 else None,
    }


def parse_work_formats(text: str | None, *, allow_shorthand_all: bool = False) -> dict:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return {}

    if any(re.search(pattern, lowered) for pattern in _ALL_FORMAT_PATTERNS):
        return build_work_formats_payload(WORK_FORMAT_ORDER)

    if allow_shorthand_all and lowered in _SHORTHAND_ALL_VALUES:
        return build_work_formats_payload(WORK_FORMAT_ORDER)

    matched = [
        work_format
        for work_format in WORK_FORMAT_ORDER
        if any(token in lowered for token in _WORK_FORMAT_SYNONYMS[work_format])
    ]
    return build_work_formats_payload(matched)


def candidate_work_formats(candidate) -> list[str]:
    if candidate is None:
        return []
    stored = normalize_work_formats(getattr(candidate, "work_formats_json", None) or [])
    if stored:
        return stored
    legacy = normalize_work_format(getattr(candidate, "work_format", None))
    return [legacy] if legacy else []


def display_work_formats(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        formats = normalize_work_formats(value)
    else:
        formats = candidate_work_formats(value)
        if not formats:
            single = normalize_work_format(getattr(value, "work_format", value))
            formats = [single] if single else []
    if not formats:
        return None
    if len(formats) == len(WORK_FORMAT_ORDER):
        return "all formats"
    if len(formats) == 1:
        return formats[0]
    return " + ".join(formats)


def primary_work_format(value) -> str | None:
    if isinstance(value, (list, tuple, set)):
        formats = normalize_work_formats(value)
    else:
        formats = candidate_work_formats(value)
    if len(formats) == 1:
        return formats[0]
    return None


def work_formats_require_city(value) -> bool:
    if isinstance(value, (list, tuple, set)):
        formats = normalize_work_formats(value)
    else:
        formats = candidate_work_formats(value)
    return any(item in {"hybrid", "office"} for item in formats)


def candidate_accepts_vacancy_work_format(candidate, vacancy_work_format: str | None) -> bool | None:
    formats = candidate_work_formats(candidate)
    vacancy_format = normalize_work_format(vacancy_work_format)
    if not formats or vacancy_format is None:
        return None
    return vacancy_format in formats
