from __future__ import annotations

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


def filter_candidate_question_payload(parsed: dict, current_question_key: str | None) -> dict:
    if not parsed or current_question_key is None:
        return dict(parsed or {})
    allowed_keys = QUESTION_ALLOWED_KEYS.get(current_question_key, set())
    return {key: value for key, value in parsed.items() if key in allowed_keys}


def enrich_candidate_question_payload_for_current_question(
    *,
    parsed: dict,
    text: str | None,
    current_question_key: str | None,
) -> dict:
    enriched = dict(parsed or {})
    if current_question_key == "work_format" and not filter_candidate_question_payload(enriched, current_question_key):
        enriched.update(parse_work_formats(text, allow_shorthand_all=True))
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
