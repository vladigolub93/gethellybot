from __future__ import annotations

import re

from src.candidate_profile.work_formats import candidate_accepts_vacancy_work_format
from src.shared.hiring_taxonomy import compare_english_levels


SENIORITY_ORDER = {
    "junior": 1,
    "middle": 2,
    "senior": 3,
}


def _normalize_city(value) -> str | None:
    text = " ".join(str(value or "").split()).strip().lower()
    if not text:
        return None
    return re.sub(r"[^a-z0-9]+", "", text)


def evaluate_hard_filters(candidate, vacancy) -> list[str]:
    reasons = []

    if vacancy.countries_allowed_json and candidate.country_code:
        if candidate.country_code not in vacancy.countries_allowed_json:
            reasons.append("location_mismatch")

    if vacancy.work_format:
        accepts_work_format = candidate_accepts_vacancy_work_format(candidate, vacancy.work_format)
        if accepts_work_format is False:
            reasons.append("work_format_mismatch")

    if vacancy.work_format in {"office", "hybrid"} and getattr(vacancy, "office_city", None):
        candidate_city = _normalize_city(getattr(candidate, "city", None))
        vacancy_city = _normalize_city(getattr(vacancy, "office_city", None))
        if not candidate_city or (vacancy_city and candidate_city != vacancy_city):
            reasons.append("office_city_mismatch")

    if vacancy.budget_max is not None and candidate.salary_min is not None:
        if float(candidate.salary_min) > float(vacancy.budget_max):
            reasons.append("salary_above_budget")

    if vacancy.seniority_normalized and candidate.seniority_normalized:
        vacancy_level = SENIORITY_ORDER.get(vacancy.seniority_normalized)
        candidate_level = SENIORITY_ORDER.get(candidate.seniority_normalized)
        if vacancy_level is not None and candidate_level is not None and candidate_level < vacancy_level:
            reasons.append("seniority_mismatch")

    english_comparison = compare_english_levels(
        getattr(candidate, "english_level", None),
        getattr(vacancy, "required_english_level", None),
    )
    if english_comparison is not None and english_comparison < 0:
        reasons.append("english_level_mismatch")

    if getattr(candidate, "show_take_home_task_roles", None) is False and getattr(vacancy, "has_take_home_task", None) is True:
        reasons.append("take_home_preference_mismatch")

    if getattr(candidate, "show_live_coding_roles", None) is False and getattr(vacancy, "has_live_coding", None) is True:
        reasons.append("live_coding_preference_mismatch")

    return reasons
