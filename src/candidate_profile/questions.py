from __future__ import annotations

import re

from src.candidate_profile.question_parser import (
    COUNTRY_CODES,
    parse_assessment_preferences,
    parse_english_level,
    parse_preferred_domains,
)
from src.candidate_profile.question_prompts import QUESTION_KEYS
from src.candidate_profile.work_formats import (
    candidate_work_formats,
    parse_work_formats,
    work_formats_require_city,
)


QUESTION_ALLOWED_KEYS = {
    "salary": {"salary_min", "salary_max", "salary_currency", "salary_period"},
    "work_format": {"work_format", "work_formats_json"},
    "location": {"location_text", "city", "country_code"},
    "english_level": {"english_level"},
    "preferred_domains": {"preferred_domains_json"},
    "assessment_preferences": {"show_take_home_task_roles", "show_live_coding_roles"},
}

_DOMAIN_NO_PREFERENCE_VALUES = {
    "any",
    "anything",
    "anything works",
    "whatever",
    "no",
    "nope",
    "нет",
    "нету",
    "никаких",
    "любые",
    "что угодно",
    "что хочешь",
    "какие угодно",
    "не имеет значения",
    "не має значення",
    "нема предпочтений",
    "немає переваг",
    "жодних",
    "без разницы",
    "без різниці",
    "не важно",
    "неважно",
    "мне все равно",
    "мне всё равно",
    "мне все рано",
}

_ASSESSMENT_ONLY_TOKENS = ("только", "лишь", "лише", "only", "just")
_ASSESSMENT_TAKE_HOME_TOKENS = (
    "take-home",
    "take home",
    "test task",
    "home assignment",
    "тестовое",
    "тестовая задача",
    "тестова задача",
    "тестовая таска",
    "тестова таска",
    "таска",
    "домашка",
)
_ASSESSMENT_LIVE_CODING_TOKENS = (
    "live coding",
    "live-coding",
    "live code",
    "coding interview",
    "pair programming",
    "лайвкодинг",
    "лайв кодинг",
)


def filter_candidate_question_payload(parsed: dict, current_question_key: str | None) -> dict:
    if not parsed or current_question_key is None:
        return dict(parsed or {})
    allowed_keys = QUESTION_ALLOWED_KEYS.get(current_question_key, set())
    return {key: value for key, value in parsed.items() if key in allowed_keys}


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _fallback_location_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).strip(" .,")
    if not normalized:
        return {}
    lowered = normalized.lower()
    country_code = COUNTRY_CODES.get(lowered)
    if country_code is not None:
        return {
            "location_text": normalized,
            "country_code": country_code,
            "city": None,
        }
    return {
        "location_text": normalized,
        "city": normalized,
    }


def _fallback_english_level_payload(text: str | None) -> dict:
    normalized = _normalize_text(text)
    if not normalized:
        return {}
    return parse_english_level(normalized)


def _fallback_preferred_domains_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return {}
    explicit = parse_preferred_domains(normalized)
    if explicit:
        return explicit
    if normalized in _DOMAIN_NO_PREFERENCE_VALUES:
        return {"preferred_domains_json": ["any"]}
    return {}


def _fallback_assessment_preferences_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return {}

    explicit = dict(parse_assessment_preferences(normalized) or {})
    if {
        "show_take_home_task_roles",
        "show_live_coding_roles",
    }.issubset(explicit):
        return explicit

    if normalized in {
        "не хочу",
        "нет",
        "ні",
        "no",
        "nope",
        "neither",
        "none",
        "никакие",
        "жодні",
    }:
        return {
            "show_take_home_task_roles": False,
            "show_live_coding_roles": False,
        }

    if normalized in {
        "готов к обоим",
        "готова к обоим",
        "готовий до обох",
        "готова до обох",
        "оба",
        "оба",
        "обоим",
        "обидва",
        "both",
        "both are fine",
        "all good",
    }:
        return {
            "show_take_home_task_roles": True,
            "show_live_coding_roles": True,
        }

    has_only = any(token in normalized for token in _ASSESSMENT_ONLY_TOKENS)
    has_take_home = any(token in normalized for token in _ASSESSMENT_TAKE_HOME_TOKENS)
    has_live_coding = any(token in normalized for token in _ASSESSMENT_LIVE_CODING_TOKENS)
    negative_take_home = bool(
        re.search(r"\b(no|nope|not|нет|ні|без)\s+(?:tests?|test task|take-home|take home|тест(?:а|ов)?|тестового|тестове|тестовая таска|тестова таска|домашка)\b", normalized)
    )
    negative_live_coding = bool(
        re.search(r"\b(no|nope|not|нет|ні|без)\s+(?:live code|live coding|live-coding|лайвкодинг|лайв кодинг)\b", normalized)
    )
    shared_negative_assessment = bool(
        re.search(
            r"\b(no|nope|not|нет|ні|без)\b.*\b(?:tests?|test task|take-home|take home|тест(?:а|ов)?|тестового|тестове|тестовая таска|тестова таска)\b.*\b(?:live code|live coding|live-coding|лайвкодинг|лайв кодинг)\b",
            normalized,
        )
    )
    if shared_negative_assessment:
        negative_take_home = True
        negative_live_coding = True

    if negative_take_home or negative_live_coding:
        payload = {}
        if negative_take_home:
            payload["show_take_home_task_roles"] = False
        if negative_live_coding:
            payload["show_live_coding_roles"] = False
        if payload:
            if "show_take_home_task_roles" not in payload and explicit.get("show_take_home_task_roles") is not None:
                payload["show_take_home_task_roles"] = explicit["show_take_home_task_roles"]
            if "show_live_coding_roles" not in payload and explicit.get("show_live_coding_roles") is not None:
                payload["show_live_coding_roles"] = explicit["show_live_coding_roles"]
            return payload

    if normalized in {
        "без лайвкодинга",
        "без лайв кодинга",
        "no live coding",
        "no live code",
        "live coding no",
        "live code no",
    }:
        return {"show_live_coding_roles": False}

    if normalized in {
        "без тестового",
        "без тестового задания",
        "без тестов",
        "no take-home",
        "no take home",
        "take-home no",
        "take home no",
    }:
        return {"show_take_home_task_roles": False}

    if normalized in {
        "только take-home",
        "only take-home",
        "only test task",
        "only test",
        "take-home only",
        "только тестовое",
        "только тестовая задача",
        "только тестовая таска",
        "только таска",
        "лише take-home",
        "лише тестове",
        "лише тестова задача",
        "лише тестова таска",
    } or (has_only and has_take_home and not has_live_coding):
        return {
            "show_take_home_task_roles": True,
            "show_live_coding_roles": False,
        }

    if normalized in {
        "только live-coding",
        "only live-coding",
        "only live coding",
        "live-coding only",
        "только лайвкодинг",
        "только лайв кодинг",
        "лише live-coding",
        "лише лайвкодинг",
    } or (has_only and has_live_coding and not has_take_home):
        return {
            "show_take_home_task_roles": False,
            "show_live_coding_roles": True,
        }

    return explicit


def enrich_candidate_question_payload_for_current_question(
    *,
    parsed: dict,
    text: str | None,
    current_question_key: str | None,
) -> dict:
    enriched = dict(parsed or {})
    filtered = filter_candidate_question_payload(enriched, current_question_key)
    if current_question_key == "work_format" and not filtered:
        enriched.update(parse_work_formats(text, allow_shorthand_all=True))
    if current_question_key == "location" and not filtered:
        enriched.update(_fallback_location_payload(text))
    if current_question_key == "english_level" and not filtered:
        enriched.update(_fallback_english_level_payload(text))
    if current_question_key == "preferred_domains" and not filtered:
        enriched.update(_fallback_preferred_domains_payload(text))
    if current_question_key == "assessment_preferences" and (
        not filtered
        or "show_take_home_task_roles" not in filtered
        or "show_live_coding_roles" not in filtered
    ):
        enriched.update(_fallback_assessment_preferences_payload(text))
    return filter_candidate_question_payload(enriched, current_question_key)


def missing_candidate_question_keys(profile) -> list[str]:
    missing = []
    salary_min = getattr(profile, "salary_min", None)
    salary_max = getattr(profile, "salary_max", None)
    work_formats = candidate_work_formats(profile)
    country_code = getattr(profile, "country_code", None)
    city = getattr(profile, "city", None)
    english_level = getattr(profile, "english_level", None)
    preferred_domains_json = list(getattr(profile, "preferred_domains_json", None) or [])
    show_take_home_task_roles = getattr(profile, "show_take_home_task_roles", None)
    show_live_coding_roles = getattr(profile, "show_live_coding_roles", None)
    if salary_min is None and salary_max is None:
        missing.append("salary")
    if not work_formats:
        missing.append("work_format")
    if not country_code or (work_formats_require_city(work_formats) and not city):
        missing.append("location")
    if not english_level:
        missing.append("english_level")
    if not preferred_domains_json:
        missing.append("preferred_domains")
    if show_take_home_task_roles is None or show_live_coding_roles is None:
        missing.append("assessment_preferences")
    return missing


def current_candidate_question_key(profile) -> str | None:
    missing = missing_candidate_question_keys(profile)
    if not missing:
        return None
    current = dict(getattr(profile, "questions_context_json", None) or {}).get("current_question_key")
    if current in QUESTION_KEYS:
        return current
    return missing[0]
