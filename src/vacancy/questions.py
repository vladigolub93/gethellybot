from __future__ import annotations

import re

from src.vacancy.question_parser import (
    parse_assessment_requirements,
    parse_budget,
    parse_countries,
    parse_hiring_stages,
    parse_office_city,
    parse_primary_tech_stack,
    parse_project_description,
    parse_required_english_level,
    parse_team_size,
    parse_work_format,
)
from src.vacancy.question_prompts import QUESTION_KEYS


CLARIFICATION_ALLOWED_KEYS = {
    "budget": {"budget_min", "budget_max", "budget_currency", "budget_period"},
    "work_format": {"work_format"},
    "office_city": {"office_city"},
    "countries": {"countries_allowed_json"},
    "english_level": {"required_english_level"},
    "assessment": {"has_take_home_task", "has_live_coding"},
    "take_home_paid": {"take_home_paid"},
    "hiring_stages": {"hiring_stages_json"},
    "team_size": {"team_size"},
    "project_description": {"project_description"},
    "primary_tech_stack": {"primary_tech_stack_json"},
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
_ASSESSMENT_NONE_VALUES = {
    "не будет",
    "не буде",
    "нет",
    "ні",
    "no",
    "neither",
    "none",
    "nothing",
    "без этапов",
    "без етапів",
    "ничего",
    "нічого",
    "ничего нет",
    "нічого нема",
    "ничего нету",
    "нічого немає",
    "нет ничего",
    "нема нічого",
    "нету ничего",
}
_AFFIRMATIVE_VALUES = {
    "yes",
    "yeah",
    "yep",
    "true",
    "да",
    "ага",
    "ok",
    "okay",
    "paid",
    "платная",
    "платний",
    "платне",
    "оплачиваемое",
    "оплачиваемый",
    "оплачуване",
    "оплачуваний",
}
_NEGATIVE_VALUES = {
    "no",
    "nope",
    "false",
    "нет",
    "ні",
    "бесплатно",
    "бесплатная",
    "бесплатный",
    "бесплатное",
    "безкоштовно",
    "безкоштовна",
    "безкоштовний",
    "безкоштовне",
    "не платная",
    "неплатная",
    "не платний",
    "неплатний",
    "не платне",
    "неплатне",
    "неоплачиваемое",
    "неоплачиваемый",
    "не оплачивается",
    "неоплачуване",
    "неоплачуваний",
    "не оплачується",
    "unpaid",
}


def filter_vacancy_clarification_payload(parsed: dict, current_question_key: str | None) -> dict:
    if not parsed or current_question_key is None:
        return dict(parsed or {})
    allowed_keys = CLARIFICATION_ALLOWED_KEYS.get(current_question_key, set())
    return {key: value for key, value in parsed.items() if key in allowed_keys}


def _has_meaningful_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _payload_has_meaningful_values(payload: dict) -> bool:
    return any(_has_meaningful_value(value) for value in (payload or {}).values())


def _payload_has_meaningful_key(payload: dict, key: str) -> bool:
    return key in (payload or {}) and _has_meaningful_value(payload.get(key))


def _normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip()


def _fallback_office_city_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).strip(" .,")
    if not normalized:
        return {}
    explicit = parse_office_city(normalized)
    if explicit:
        return explicit
    return {"office_city": normalized}


def _fallback_required_english_level_payload(text: str | None) -> dict:
    normalized = _normalize_text(text)
    if not normalized:
        return {}
    return parse_required_english_level(normalized)


def _fallback_assessment_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).lower().strip(" .,!?:;")
    if not normalized:
        return {}

    explicit = dict(parse_assessment_requirements(normalized) or {})
    if {
        "has_take_home_task",
        "has_live_coding",
    }.issubset(explicit):
        return explicit

    if normalized in _ASSESSMENT_NONE_VALUES:
        return {
            "has_take_home_task": False,
            "has_live_coding": False,
        }

    if normalized in {
        "оба",
        "оба ок",
        "both",
        "both are fine",
        "и то и то",
        "и то, и то",
        "обидва",
    }:
        return {
            "has_take_home_task": True,
            "has_live_coding": True,
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
            payload["has_take_home_task"] = False
        if negative_live_coding:
            payload["has_live_coding"] = False
        if payload:
            if "has_take_home_task" not in payload and explicit.get("has_take_home_task") is not None:
                payload["has_take_home_task"] = explicit["has_take_home_task"]
            if "has_live_coding" not in payload and explicit.get("has_live_coding") is not None:
                payload["has_live_coding"] = explicit["has_live_coding"]
            return payload

    if normalized in {
        "без лайвкодинга",
        "без лайв кодинга",
        "no live coding",
        "no live code",
        "live coding no",
        "live code no",
    }:
        return {"has_live_coding": False}

    if normalized in {
        "без тестового",
        "без тестового задания",
        "без тестов",
        "no take-home",
        "no take home",
        "take-home no",
        "take home no",
    }:
        return {"has_take_home_task": False}

    if (has_only and has_take_home and not has_live_coding) or normalized in {
        "only take-home",
        "only test task",
        "take-home only",
        "только тестовое",
        "только тестовая таска",
        "только тестовая задача",
        "только таска",
        "лише тестове",
        "лише тестова задача",
        "лише тестова таска",
    }:
        return {
            "has_take_home_task": True,
            "has_live_coding": False,
        }

    if (has_only and has_live_coding and not has_take_home) or normalized in {
        "only live-coding",
        "only live coding",
        "live-coding only",
        "только лайвкодинг",
        "только лайв кодинг",
        "лише лайвкодинг",
    }:
        return {
            "has_take_home_task": False,
            "has_live_coding": True,
        }

    return explicit


def _fallback_take_home_paid_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return {}
    explicit = dict(parse_assessment_requirements(normalized) or {})
    if "take_home_paid" in explicit:
        return {"take_home_paid": explicit["take_home_paid"]}
    if normalized in _AFFIRMATIVE_VALUES:
        return {"take_home_paid": True}
    if normalized in _NEGATIVE_VALUES:
        return {"take_home_paid": False}
    return {}


def _fallback_team_size_payload(text: str | None) -> dict:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return {}
    explicit = parse_team_size(normalized)
    if explicit:
        return explicit
    match = re.fullmatch(r"(\d{1,3})", normalized)
    if match is None:
        return {}
    return {"team_size": int(match.group(1))}


def _fallback_project_description_payload(text: str | None) -> dict:
    normalized = _normalize_text(text)
    if not normalized:
        return {}
    explicit = parse_project_description(normalized)
    if explicit:
        return explicit
    if len(normalized.split()) >= 4:
        return {"project_description": normalized}
    return {}


def enrich_vacancy_clarification_payload_for_current_question(
    *,
    parsed: dict,
    text: str | None,
    current_question_key: str | None,
) -> dict:
    enriched = dict(parsed or {})
    filtered = filter_vacancy_clarification_payload(enriched, current_question_key)

    if current_question_key == "budget" and not _payload_has_meaningful_values(filtered):
        enriched.update(parse_budget(text or ""))
    if current_question_key == "work_format" and not _payload_has_meaningful_values(filtered):
        enriched.update(parse_work_format(text or ""))
    if current_question_key == "office_city" and not _payload_has_meaningful_values(filtered):
        enriched.update(_fallback_office_city_payload(text))
    if current_question_key == "countries" and not _payload_has_meaningful_values(filtered):
        enriched.update(parse_countries(text or ""))
    if current_question_key == "english_level" and not _payload_has_meaningful_values(filtered):
        enriched.update(_fallback_required_english_level_payload(text))
    if current_question_key == "assessment" and (
        not _payload_has_meaningful_key(filtered, "has_take_home_task")
        or not _payload_has_meaningful_key(filtered, "has_live_coding")
    ):
        enriched.update(_fallback_assessment_payload(text))
    if current_question_key == "take_home_paid" and not _payload_has_meaningful_values(filtered):
        enriched.update(_fallback_take_home_paid_payload(text))
    if current_question_key == "hiring_stages" and not _payload_has_meaningful_values(filtered):
        enriched.update(parse_hiring_stages(text or ""))
    if current_question_key == "team_size" and not _payload_has_meaningful_values(filtered):
        enriched.update(_fallback_team_size_payload(text))
    if current_question_key == "project_description" and not _payload_has_meaningful_values(filtered):
        enriched.update(_fallback_project_description_payload(text))
    if current_question_key == "primary_tech_stack" and not _payload_has_meaningful_values(filtered):
        enriched.update(parse_primary_tech_stack(text or ""))
    return filter_vacancy_clarification_payload(enriched, current_question_key)


def required_vacancy_clarification_keys(vacancy) -> list[str]:
    required = [
        "budget",
        "work_format",
        "countries",
        "english_level",
        "assessment",
        "hiring_stages",
        "team_size",
        "project_description",
        "primary_tech_stack",
    ]
    if getattr(vacancy, "work_format", None) in {"office", "hybrid"}:
        required.insert(2, "office_city")
    if getattr(vacancy, "has_take_home_task", None) is True:
        required.insert(required.index("hiring_stages"), "take_home_paid")
    return required


def missing_vacancy_clarification_keys(vacancy, *, confirmed_fields: set[str] | None = None) -> list[str]:
    required_keys = required_vacancy_clarification_keys(vacancy)
    if confirmed_fields is not None:
        return [key for key in required_keys if key not in confirmed_fields]

    questions_context = dict(getattr(vacancy, "questions_context_json", None) or {})
    if "confirmed_fields" in questions_context:
        stored_confirmed_fields = set(questions_context.get("confirmed_fields") or [])
        return [key for key in required_keys if key not in stored_confirmed_fields]

    missing = []
    if getattr(vacancy, "budget_min", None) is None and getattr(vacancy, "budget_max", None) is None:
        missing.append("budget")
    if not getattr(vacancy, "work_format", None):
        missing.append("work_format")
    if getattr(vacancy, "work_format", None) in {"office", "hybrid"} and not getattr(vacancy, "office_city", None):
        missing.append("office_city")
    if not getattr(vacancy, "countries_allowed_json", None):
        missing.append("countries")
    if not getattr(vacancy, "required_english_level", None):
        missing.append("english_level")
    if getattr(vacancy, "has_take_home_task", None) is None or getattr(vacancy, "has_live_coding", None) is None:
        missing.append("assessment")
    if getattr(vacancy, "has_take_home_task", None) is True and getattr(vacancy, "take_home_paid", None) is None:
        missing.append("take_home_paid")
    if not getattr(vacancy, "hiring_stages_json", None):
        missing.append("hiring_stages")
    if getattr(vacancy, "team_size", None) is None:
        missing.append("team_size")
    if not getattr(vacancy, "project_description", None):
        missing.append("project_description")
    if not getattr(vacancy, "primary_tech_stack_json", None):
        missing.append("primary_tech_stack")
    return missing


def current_vacancy_question_key(vacancy) -> str | None:
    missing = missing_vacancy_clarification_keys(vacancy)
    if not missing:
        return None
    current = dict(getattr(vacancy, "questions_context_json", None) or {}).get("current_question_key")
    if current in QUESTION_KEYS:
        return current
    return missing[0]
