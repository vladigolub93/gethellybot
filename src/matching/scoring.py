from __future__ import annotations

import re
from math import sqrt

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
    if candidate_work_format and vacancy_work_format:
        work_format_fit = 1.0 if str(candidate_work_format).lower() == str(vacancy_work_format).lower() else 0.0

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

    total_score = round(
        (core_overlap_ratio * 0.32)
        + (full_overlap_ratio * 0.20)
        + (experience_score * 0.13)
        + (seniority_fit * 0.10)
        + (role_fit * 0.10)
        + (work_format_fit * 0.03)
        + (location_fit * 0.02)
        + (english_fit * 0.03)
        + (domain_fit * 0.04)
        + (process_fit * 0.03),
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
    }
