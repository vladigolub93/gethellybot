from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.candidate_profile.work_formats import display_work_formats
from src.shared.hiring_taxonomy import (
    display_domains,
    display_english_level,
    display_hiring_stages,
)


def _clean_text(value: str | None, *, limit: int = 420) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return None
    return normalized[:limit]


def _clean_list(values, *, item_limit: int = 8, item_text_limit: int = 80) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        cleaned = _clean_text(str(value or ""), limit=item_text_limit)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= item_limit:
            break
    return result


def _compact(value: Any):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            compacted = _compact(item)
            if compacted in (None, "", [], {}):
                continue
            result[key] = compacted
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            compacted = _compact(item)
            if compacted in (None, "", [], {}):
                continue
            result.append(compacted)
        return result
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _match_rationale(match) -> dict:
    rationale = getattr(match, "rationale_json", None) or {}
    return _compact(
        {
            "fit_band": _clean_text(rationale.get("fit_band"), limit=32),
            "matched_signals": _clean_list(rationale.get("matched_signals"), item_limit=5, item_text_limit=120),
            "gap_signals": _clean_list(rationale.get("gap_signals"), item_limit=4, item_text_limit=120),
            "llm_rationale": _clean_text(rationale.get("llm_rationale"), limit=220),
        }
    )


def _effective_hiring_stages(vacancy) -> list[str]:
    hiring_stages = display_hiring_stages(getattr(vacancy, "hiring_stages_json", None))
    if not hiring_stages:
        return []
    if getattr(vacancy, "has_take_home_task", None) is False:
        hiring_stages = [stage for stage in hiring_stages if stage.lower() != "take-home task"]
    if getattr(vacancy, "has_live_coding", None) is False:
        hiring_stages = [stage for stage in hiring_stages if stage.lower() != "live coding"]
    return hiring_stages


def build_candidate_review_dossier(*, match, vacancy, vacancy_version) -> dict:
    summary_json = getattr(vacancy_version, "summary_json", None) or {}
    approval_summary = _clean_text(
        getattr(vacancy_version, "approval_summary_text", None)
        or summary_json.get("approval_summary_text"),
        limit=260,
    )
    project_description = _clean_text(getattr(vacancy, "project_description", None), limit=320)
    dossier = {
        "scope": "current vacancy review card only",
        "role_title": _clean_text(getattr(vacancy, "role_title", None), limit=120),
        "match_status": _clean_text(getattr(match, "status", None), limit=64),
        "match_rationale": _match_rationale(match),
        "vacancy": {
            "role_title": _clean_text(getattr(vacancy, "role_title", None), limit=120),
            "seniority": _clean_text(getattr(vacancy, "seniority_normalized", None), limit=60),
            "budget_min": getattr(vacancy, "budget_min", None),
            "budget_max": getattr(vacancy, "budget_max", None),
            "budget_currency": _clean_text(getattr(vacancy, "budget_currency", None), limit=12),
            "budget_period": _clean_text(getattr(vacancy, "budget_period", None), limit=32),
            "work_format": _clean_text(getattr(vacancy, "work_format", None), limit=32),
            "office_city": _clean_text(getattr(vacancy, "office_city", None), limit=80),
            "countries_allowed": _clean_list(getattr(vacancy, "countries_allowed_json", None), item_limit=8, item_text_limit=16),
            "required_english_level": display_english_level(getattr(vacancy, "required_english_level", None)),
            "team_size": getattr(vacancy, "team_size", None),
            "project_description": project_description,
            "primary_tech_stack": _clean_list(getattr(vacancy, "primary_tech_stack_json", None), item_limit=10),
            "hiring_stages": _effective_hiring_stages(vacancy),
            "has_take_home_task": getattr(vacancy, "has_take_home_task", None),
            "take_home_paid": getattr(vacancy, "take_home_paid", None),
            "has_live_coding": getattr(vacancy, "has_live_coding", None),
        },
        "vacancy_summary": {
            "source_type": _clean_text(getattr(vacancy_version, "source_type", None), limit=60),
            "approval_summary_text": approval_summary,
            "project_description_excerpt": _clean_text(summary_json.get("project_description_excerpt"), limit=220),
            "role_title": _clean_text(summary_json.get("role_title"), limit=120),
            "seniority": _clean_text(summary_json.get("seniority_normalized"), limit=60),
            "primary_tech_stack": _clean_list(
                summary_json.get("primary_tech_stack") or summary_json.get("primary_tech_stack_json"),
                item_limit=10,
            ),
        },
        "source_excerpts": {
            "extracted_text_excerpt": _clean_text(getattr(vacancy_version, "extracted_text", None), limit=360),
            "transcript_excerpt": _clean_text(getattr(vacancy_version, "transcript_text", None), limit=360),
        },
        "source_availability": {
            "has_project_description": bool(project_description),
            "has_summary": bool(approval_summary),
            "has_extracted_text_excerpt": bool(_clean_text(getattr(vacancy_version, "extracted_text", None), limit=360)),
            "has_transcript_excerpt": bool(_clean_text(getattr(vacancy_version, "transcript_text", None), limit=360)),
        },
        "available_sections": [
            name
            for name, value in (
                ("project_description", project_description),
                ("team_size", getattr(vacancy, "team_size", None)),
                ("budget", getattr(vacancy, "budget_min", None) or getattr(vacancy, "budget_max", None)),
                ("setup", getattr(vacancy, "work_format", None) or getattr(vacancy, "countries_allowed_json", None)),
                ("english_level", display_english_level(getattr(vacancy, "required_english_level", None))),
                ("primary_tech_stack", getattr(vacancy, "primary_tech_stack_json", None)),
                ("hiring_stages", _effective_hiring_stages(vacancy)),
                ("summary", approval_summary),
                ("source_excerpt", _clean_text(getattr(vacancy_version, "extracted_text", None), limit=360)),
            )
            if value not in (None, "", [])
        ],
        "known_missing_fields": [
            name
            for name, value in (
                ("project_description", project_description),
                ("team_size", getattr(vacancy, "team_size", None)),
                ("budget", getattr(vacancy, "budget_min", None) or getattr(vacancy, "budget_max", None)),
                ("required_english_level", display_english_level(getattr(vacancy, "required_english_level", None))),
                ("primary_tech_stack", getattr(vacancy, "primary_tech_stack_json", None)),
            )
            if value in (None, "", [])
        ],
    }
    return _compact(dossier)


def build_manager_review_dossier(
    *,
    match,
    vacancy,
    candidate,
    candidate_version,
    latest_verification=None,
    evaluation_result=None,
) -> dict:
    summary_json = getattr(candidate_version, "summary_json", None) or {}
    extracted_text_excerpt = _clean_text(getattr(candidate_version, "extracted_text", None), limit=360)
    transcript_excerpt = _clean_text(getattr(candidate_version, "transcript_text", None), limit=360)
    dossier = {
        "scope": "current candidate review card only",
        "vacancy_role_title": _clean_text(getattr(vacancy, "role_title", None), limit=120),
        "match_status": _clean_text(getattr(match, "status", None), limit=64),
        "match_rationale": _match_rationale(match),
        "candidate": {
            "target_role": _clean_text(getattr(candidate, "target_role", None), limit=120),
            "seniority": _clean_text(getattr(candidate, "seniority_normalized", None), limit=60),
            "salary_min": getattr(candidate, "salary_min", None),
            "salary_max": getattr(candidate, "salary_max", None),
            "salary_currency": _clean_text(getattr(candidate, "salary_currency", None), limit=12),
            "salary_period": _clean_text(getattr(candidate, "salary_period", None), limit=32),
            "location_text": _clean_text(getattr(candidate, "location_text", None), limit=120),
            "country_code": _clean_text(getattr(candidate, "country_code", None), limit=12),
            "city": _clean_text(getattr(candidate, "city", None), limit=80),
            "work_formats": display_work_formats(candidate),
            "english_level": display_english_level(getattr(candidate, "english_level", None)),
            "preferred_domains": display_domains(getattr(candidate, "preferred_domains_json", None)),
            "show_take_home_task_roles": getattr(candidate, "show_take_home_task_roles", None),
            "show_live_coding_roles": getattr(candidate, "show_live_coding_roles", None),
        },
        "candidate_summary": {
            "source_type": _clean_text(getattr(candidate_version, "source_type", None), limit=60),
            "headline": _clean_text(summary_json.get("headline"), limit=180),
            "experience_excerpt": _clean_text(summary_json.get("experience_excerpt"), limit=260),
            "approval_summary_text": _clean_text(summary_json.get("approval_summary_text"), limit=260),
            "years_experience": summary_json.get("years_experience"),
            "skills": _clean_list(summary_json.get("skills"), item_limit=12),
        },
        "verification": {
            "latest_submitted_status": _clean_text(getattr(latest_verification, "status", None), limit=32),
            "latest_submitted_attempt_no": getattr(latest_verification, "attempt_no", None),
            "submitted_at": str(getattr(latest_verification, "submitted_at", None)) if latest_verification else None,
        },
        "evaluation": {
            "status": _clean_text(getattr(evaluation_result, "status", None), limit=32),
            "final_score": getattr(evaluation_result, "final_score", None),
            "recommendation": _clean_text(getattr(evaluation_result, "recommendation", None), limit=120),
            "strengths": _clean_list(getattr(evaluation_result, "strengths_json", None), item_limit=5, item_text_limit=140),
            "risks": _clean_list(getattr(evaluation_result, "risks_json", None), item_limit=5, item_text_limit=140),
        },
        "source_excerpts": {
            "extracted_text_excerpt": extracted_text_excerpt,
            "transcript_excerpt": transcript_excerpt,
        },
        "source_availability": {
            "has_summary": bool(
                _clean_text(summary_json.get("approval_summary_text"), limit=260)
                or _clean_text(summary_json.get("experience_excerpt"), limit=260)
            ),
            "has_skills": bool(_clean_list(summary_json.get("skills"), item_limit=12)),
            "has_extracted_text_excerpt": bool(extracted_text_excerpt),
            "has_transcript_excerpt": bool(transcript_excerpt),
            "has_verification": bool(getattr(latest_verification, "status", None)),
            "has_evaluation": bool(getattr(evaluation_result, "status", None)),
        },
        "available_sections": [
            name
            for name, value in (
                ("summary", summary_json.get("approval_summary_text") or summary_json.get("experience_excerpt")),
                ("skills", summary_json.get("skills")),
                ("salary", getattr(candidate, "salary_min", None) or getattr(candidate, "salary_max", None)),
                ("location", getattr(candidate, "location_text", None) or getattr(candidate, "country_code", None)),
                ("work_formats", display_work_formats(candidate)),
                ("english_level", display_english_level(getattr(candidate, "english_level", None))),
                ("domains", display_domains(getattr(candidate, "preferred_domains_json", None))),
                ("assessment_preferences", getattr(candidate, "show_take_home_task_roles", None)),
                ("verification", getattr(latest_verification, "status", None)),
                ("evaluation", getattr(evaluation_result, "status", None)),
                ("resume_excerpt", extracted_text_excerpt),
            )
            if value not in (None, "", [])
        ],
        "known_missing_fields": [
            name
            for name, value in (
                ("summary", summary_json.get("approval_summary_text") or summary_json.get("experience_excerpt")),
                ("skills", summary_json.get("skills")),
                ("english_level", display_english_level(getattr(candidate, "english_level", None))),
                ("location", getattr(candidate, "location_text", None)),
                ("verification", getattr(latest_verification, "status", None)),
                ("evaluation", getattr(evaluation_result, "status", None)),
            )
            if value in (None, "", [])
        ],
    }
    return _compact(dossier)
