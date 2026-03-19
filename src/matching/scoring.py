from __future__ import annotations

import re
from math import sqrt

from src.candidate_profile.work_formats import candidate_accepts_vacancy_work_format, candidate_work_formats
from src.candidate_profile.skills_inventory import normalize_skill_list
from src.shared.hiring_taxonomy import compare_english_levels, extract_domains


def _as_set(values) -> set[str]:
    return set(normalize_skill_list(values))


def _normalize_role_tokens(value) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    if not normalized:
        return set()
    stopwords = {"engineer", "developer", "specialist", "lead", "software"}
    return {token for token in normalized.split() if token and token not in stopwords}


def _normalize_hiring_stages(values) -> list[str]:
    stages = []
    seen = set()
    for value in values or []:
        normalized = str(value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        stages.append(normalized)
    return stages


def _normalize_feedback_categories(values) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


FIT_BAND_PRIORITY = {
    "strong": 0,
    "medium": 1,
    "low": 2,
    "not_fit": 3,
}


def fit_band_label(value: str | None) -> str | None:
    labels = {
        "strong": "Strong fit",
        "medium": "Medium fit",
        "low": "Low fit",
        "not_fit": "Not fit",
    }
    normalized = str(value or "").strip().lower()
    return labels.get(normalized)


def _compute_process_fit(
    *,
    candidate_show_take_home_task_roles,
    candidate_show_live_coding_roles,
    vacancy_has_take_home_task,
    vacancy_take_home_paid,
    vacancy_has_live_coding,
    vacancy_hiring_stages,
) -> float:
    stage_values = _normalize_hiring_stages(vacancy_hiring_stages)
    if (
        vacancy_has_take_home_task is None
        and vacancy_take_home_paid is None
        and vacancy_has_live_coding is None
        and not stage_values
    ):
        return 0.5

    score = 1.0
    if vacancy_has_take_home_task:
        if candidate_show_take_home_task_roles is False:
            return 0.0
        score -= 0.15
        if vacancy_take_home_paid is False:
            score -= 0.10
        elif vacancy_take_home_paid is True:
            score += 0.05

    if vacancy_has_live_coding:
        if candidate_show_live_coding_roles is False:
            return 0.0
        score -= 0.08

    stage_count = len(stage_values)
    if stage_count >= 5:
        score -= 0.15
    elif stage_count == 4:
        score -= 0.10
    elif stage_count == 3:
        score -= 0.05

    return round(max(0.0, min(1.0, score)), 4)


def _compute_compensation_fit(
    *,
    candidate_salary_min,
    candidate_salary_max,
    vacancy_budget_min,
    vacancy_budget_max,
) -> float:
    candidate_floor = candidate_salary_min if candidate_salary_min is not None else candidate_salary_max
    candidate_ceiling = candidate_salary_max if candidate_salary_max is not None else candidate_salary_min
    vacancy_floor = vacancy_budget_min if vacancy_budget_min is not None else vacancy_budget_max
    vacancy_ceiling = vacancy_budget_max if vacancy_budget_max is not None else vacancy_budget_min

    if candidate_floor is None or vacancy_ceiling is None:
        return 0.5

    if float(candidate_floor) > float(vacancy_ceiling):
        return 0.0

    if candidate_ceiling is not None and vacancy_ceiling is not None and float(candidate_ceiling) <= float(vacancy_ceiling):
        candidate_gap = float(vacancy_ceiling) - float(candidate_ceiling)
    else:
        candidate_gap = float(vacancy_ceiling) - float(candidate_floor)

    headroom_ratio = candidate_gap / max(float(vacancy_ceiling), 1.0)
    if headroom_ratio >= 0.2:
        return 1.0
    if headroom_ratio >= 0.1:
        return 0.85
    if headroom_ratio >= 0.0:
        return 0.65

    if vacancy_floor is not None and float(candidate_floor) <= float(vacancy_floor):
        return 1.0
    return 0.5


def _compute_feedback_fit(
    *,
    candidate_feedback_categories,
    vacancy_feedback_categories,
    core_overlap_ratio: float,
    full_overlap_ratio: float,
    experience_score: float,
    seniority_fit: float,
    role_fit: float,
    work_format_fit: float,
    location_fit: float,
    english_fit: float,
    domain_fit: float,
    process_fit: float,
    compensation_fit: float,
) -> tuple[float, list[str]]:
    categories = _normalize_feedback_categories(
        [*(candidate_feedback_categories or []), *(vacancy_feedback_categories or [])]
    )
    if not categories:
        return 0.5, []

    category_scores: list[float] = []
    for category in categories:
        if category == "compensation":
            category_scores.append(compensation_fit)
        elif category == "location":
            category_scores.append(round((work_format_fit + location_fit) / 2.0, 4))
        elif category == "english":
            category_scores.append(english_fit)
        elif category == "domain":
            category_scores.append(domain_fit)
        elif category == "process":
            category_scores.append(process_fit)
        elif category == "stack":
            category_scores.append(round((core_overlap_ratio + full_overlap_ratio) / 2.0, 4))
        elif category == "role":
            category_scores.append(round((role_fit + seniority_fit + experience_score) / 3.0, 4))

    if not category_scores:
        return 0.5, categories

    feedback_fit = sum(category_scores) / len(category_scores)
    return round(max(0.0, min(1.0, feedback_fit)), 4), categories


def build_gap_signals(*, score_breakdown: dict) -> list[str]:
    gaps: list[str] = []
    feedback_categories = set(_normalize_feedback_categories(score_breakdown.get("feedback_categories") or []))
    if "process" in feedback_categories and float(score_breakdown.get("process_fit") or 0.0) < 0.7:
        gaps.append("This role still misses saved hiring-process preferences.")
    if "compensation" in feedback_categories and float(score_breakdown.get("compensation_fit") or 0.0) < 0.75:
        gaps.append("Compensation still looks close to a saved mismatch point.")
    if "location" in feedback_categories and (
        float(score_breakdown.get("work_format_fit") or 0.0) < 1.0
        or float(score_breakdown.get("location_fit") or 0.0) < 0.75
    ):
        gaps.append("Location or work-format fit still misses saved preferences.")
    if "english" in feedback_categories and float(score_breakdown.get("english_fit") or 0.0) < 1.0:
        gaps.append("English fit still looks weaker than recent feedback suggests.")
    if "stack" in feedback_categories and float(score_breakdown.get("full_skill_overlap_ratio") or 0.0) < 0.65:
        gaps.append("Stack overlap still misses a recent feedback theme.")
    if "role" in feedback_categories and float(score_breakdown.get("role_fit") or 0.0) < 0.55:
        gaps.append("Role alignment still misses a recent feedback theme.")
    if "domain" in feedback_categories and float(score_breakdown.get("domain_fit") or 0.0) < 0.45:
        gaps.append("Domain fit still looks weaker than recent feedback suggests.")

    if float(score_breakdown.get("core_skill_overlap_ratio") or 0.0) < 0.65:
        gaps.append("Core stack overlap is partial.")
    if float(score_breakdown.get("role_fit") or 0.0) < 0.45:
        gaps.append("Role alignment is not exact.")
    if float(score_breakdown.get("experience_score") or 0.0) < 0.5:
        gaps.append("Experience level is closer to the lower bound of the role.")
    if float(score_breakdown.get("domain_fit") or 0.0) < 0.35:
        gaps.append("Domain background is not a close match.")
    if float(score_breakdown.get("process_fit") or 0.0) < 0.7:
        gaps.append("Hiring process may feel heavier than ideal.")
    return gaps[:3]


def classify_fit_band(
    *,
    deterministic_score: float,
    llm_fit_score: float | None,
    score_breakdown: dict,
) -> str:
    if float(score_breakdown.get("core_skill_overlap_ratio") or 0.0) < 0.2:
        return "not_fit"

    effective_score = float(llm_fit_score if llm_fit_score is not None else deterministic_score or 0.0)
    full_overlap = float(score_breakdown.get("full_skill_overlap_ratio") or 0.0)
    role_fit = float(score_breakdown.get("role_fit") or 0.0)
    process_fit = float(score_breakdown.get("process_fit") or 0.0)

    if (
        effective_score >= 0.8
        and full_overlap >= 0.7
        and role_fit >= 0.45
        and process_fit >= 0.55
    ):
        return "strong"
    if effective_score >= 0.62 and full_overlap >= 0.45:
        return "medium"
    if effective_score >= 0.4:
        return "low"
    return "not_fit"


def compute_skill_seed_score(
    *,
    candidate_core_skills,
    candidate_full_skills,
    vacancy_skills,
) -> float:
    vacancy_set = _as_set(vacancy_skills)
    if not vacancy_set:
        return 0.0

    candidate_core_set = _as_set(candidate_core_skills)
    candidate_full_set = _as_set(candidate_full_skills) | candidate_core_set
    core_overlap_ratio = len(candidate_core_set & vacancy_set) / len(vacancy_set)
    full_overlap_ratio = len(candidate_full_set & vacancy_set) / len(vacancy_set)
    return round((core_overlap_ratio * 0.65) + (full_overlap_ratio * 0.35), 4)


def has_embedding_values(embedding) -> bool:
    if embedding is None:
        return False
    try:
        return len(embedding) > 0
    except TypeError:
        return False


def compute_embedding_score(candidate_skills, vacancy_skills) -> float:
    candidate_set = _as_set(candidate_skills)
    vacancy_set = _as_set(vacancy_skills)
    if not candidate_set or not vacancy_set:
        return 0.0
    intersection = len(candidate_set & vacancy_set)
    union = len(candidate_set | vacancy_set)
    return round(intersection / union, 4)


def compute_vector_similarity(candidate_embedding, vacancy_embedding) -> float | None:
    if not has_embedding_values(candidate_embedding) or not has_embedding_values(vacancy_embedding):
        return None
    if len(candidate_embedding) != len(vacancy_embedding):
        return None
    candidate_norm = sqrt(sum(float(value) ** 2 for value in candidate_embedding))
    vacancy_norm = sqrt(sum(float(value) ** 2 for value in vacancy_embedding))
    if not candidate_norm or not vacancy_norm:
        return None
    dot_product = sum(float(a) * float(b) for a, b in zip(candidate_embedding, vacancy_embedding))
    similarity = dot_product / (candidate_norm * vacancy_norm)
    return round(max(0.0, min(1.0, similarity)), 4)


def compute_deterministic_score(
    *,
    candidate_core_skills,
    candidate_full_skills,
    vacancy_skills,
    candidate_years_experience,
    vacancy_seniority,
    candidate_seniority,
    candidate_target_role=None,
    vacancy_role_title=None,
    candidate_work_format=None,
    candidate_work_formats_json=None,
    vacancy_work_format=None,
    candidate_country_code=None,
    candidate_city=None,
    candidate_english_level=None,
    candidate_preferred_domains=None,
    vacancy_countries_allowed=None,
    vacancy_office_city=None,
    vacancy_required_english_level=None,
    vacancy_project_description=None,
    candidate_show_take_home_task_roles=None,
    candidate_show_live_coding_roles=None,
    vacancy_has_take_home_task=None,
    vacancy_take_home_paid=None,
    vacancy_has_live_coding=None,
    vacancy_hiring_stages=None,
    candidate_salary_min=None,
    candidate_salary_max=None,
    vacancy_budget_min=None,
    vacancy_budget_max=None,
    candidate_feedback_categories=None,
    vacancy_feedback_categories=None,
) -> tuple[float, dict]:
    candidate_core_set = _as_set(candidate_core_skills)
    candidate_full_set = _as_set(candidate_full_skills) | candidate_core_set
    vacancy_set = _as_set(vacancy_skills)
    required = len(vacancy_set) or 1
    core_overlap_ratio = len(candidate_core_set & vacancy_set) / required
    full_overlap_ratio = len(candidate_full_set & vacancy_set) / required

    experience_score = 0.0
    if candidate_years_experience is not None:
        experience_score = min(float(candidate_years_experience) / 10.0, 1.0)

    seniority_fit = 1.0 if candidate_seniority and candidate_seniority == vacancy_seniority else 0.5
    if not vacancy_seniority or not candidate_seniority:
        seniority_fit = 0.5

    role_fit = 0.5
    role_candidate_tokens = _normalize_role_tokens(candidate_target_role)
    role_vacancy_tokens = _normalize_role_tokens(vacancy_role_title)
    if role_candidate_tokens and role_vacancy_tokens:
        overlap = len(role_candidate_tokens & role_vacancy_tokens)
        union = len(role_candidate_tokens | role_vacancy_tokens) or 1
        role_fit = overlap / union

    work_format_fit = 0.5
    candidate_work_format_state = type(
        "_WorkFormatCandidate",
        (),
        {
            "work_format": candidate_work_format,
            "work_formats_json": candidate_work_formats_json,
        },
    )()
    if candidate_work_formats(candidate_work_format_state) and vacancy_work_format:
        work_format_fit = 1.0 if candidate_accepts_vacancy_work_format(candidate_work_format_state, vacancy_work_format) else 0.0

    english_fit = 0.5
    english_comparison = compare_english_levels(candidate_english_level, vacancy_required_english_level)
    if english_comparison is not None:
        english_fit = 1.0 if english_comparison >= 0 else 0.0

    location_fit = 0.5
    if vacancy_work_format in {"office", "hybrid"} and vacancy_office_city:
        normalized_candidate_city = re.sub(r"[^a-z0-9]+", "", str(candidate_city or "").lower())
        normalized_vacancy_city = re.sub(r"[^a-z0-9]+", "", str(vacancy_office_city or "").lower())
        location_fit = 1.0 if normalized_candidate_city and normalized_candidate_city == normalized_vacancy_city else 0.0
    elif candidate_country_code and vacancy_countries_allowed:
        location_fit = 1.0 if candidate_country_code in set(vacancy_countries_allowed or []) else 0.0

    domain_fit = 0.5
    candidate_domains = {str(value).strip().lower() for value in (candidate_preferred_domains or []) if value}
    vacancy_domains = set(extract_domains(vacancy_project_description))
    if "any" in candidate_domains:
        domain_fit = 1.0
    elif candidate_domains and vacancy_domains:
        overlap = len(candidate_domains & vacancy_domains)
        union = len(candidate_domains | vacancy_domains) or 1
        domain_fit = overlap / union if overlap else 0.0

    process_fit = _compute_process_fit(
        candidate_show_take_home_task_roles=candidate_show_take_home_task_roles,
        candidate_show_live_coding_roles=candidate_show_live_coding_roles,
        vacancy_has_take_home_task=vacancy_has_take_home_task,
        vacancy_take_home_paid=vacancy_take_home_paid,
        vacancy_has_live_coding=vacancy_has_live_coding,
        vacancy_hiring_stages=vacancy_hiring_stages,
    )
    compensation_fit = _compute_compensation_fit(
        candidate_salary_min=candidate_salary_min,
        candidate_salary_max=candidate_salary_max,
        vacancy_budget_min=vacancy_budget_min,
        vacancy_budget_max=vacancy_budget_max,
    )
    feedback_fit, feedback_categories = _compute_feedback_fit(
        candidate_feedback_categories=candidate_feedback_categories,
        vacancy_feedback_categories=vacancy_feedback_categories,
        core_overlap_ratio=core_overlap_ratio,
        full_overlap_ratio=full_overlap_ratio,
        experience_score=experience_score,
        seniority_fit=seniority_fit,
        role_fit=role_fit,
        work_format_fit=work_format_fit,
        location_fit=location_fit,
        english_fit=english_fit,
        domain_fit=domain_fit,
        process_fit=process_fit,
        compensation_fit=compensation_fit,
    )

    total_score = round(
        (core_overlap_ratio * 0.30)
        + (full_overlap_ratio * 0.19)
        + (experience_score * 0.12)
        + (seniority_fit * 0.10)
        + (role_fit * 0.10)
        + (work_format_fit * 0.03)
        + (location_fit * 0.02)
        + (english_fit * 0.03)
        + (domain_fit * 0.04)
        + (process_fit * 0.02)
        + (feedback_fit * 0.05),
        4,
    )
    return total_score, {
        "core_skill_overlap_ratio": round(core_overlap_ratio, 4),
        "full_skill_overlap_ratio": round(full_overlap_ratio, 4),
        "experience_score": round(experience_score, 4),
        "seniority_fit": round(seniority_fit, 4),
        "role_fit": round(role_fit, 4),
        "work_format_fit": round(work_format_fit, 4),
        "location_fit": round(location_fit, 4),
        "english_fit": round(english_fit, 4),
        "domain_fit": round(domain_fit, 4),
        "process_fit": round(process_fit, 4),
        "compensation_fit": round(compensation_fit, 4),
        "feedback_fit": round(feedback_fit, 4),
        "feedback_categories": feedback_categories,
    }
