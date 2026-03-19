from __future__ import annotations

from src.candidate_profile.work_formats import display_work_formats


def _clean_list(values) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = " ".join(str(value).split()).strip()
        if text:
            result.append(text)
    return result


def build_candidate_package(
    *,
    candidate_user,
    candidate_summary: dict,
    candidate_profile,
    vacancy,
    evaluation: dict,
    verification,
) -> dict:
    approval_summary = (candidate_summary or {}).get("approval_summary_text")
    skills = _clean_list((candidate_summary or {}).get("skills"))
    work_preferences = []
    if getattr(candidate_profile, "location_text", None):
        work_preferences.append(f"Location: {candidate_profile.location_text}")
    candidate_work_formats = display_work_formats(candidate_profile)
    if candidate_work_formats:
        work_preferences.append(f"Work format: {candidate_work_formats}")
    if getattr(candidate_profile, "salary_min", None) is not None:
        salary_bits = [str(candidate_profile.salary_min)]
        if getattr(candidate_profile, "salary_currency", None):
            salary_bits.append(str(candidate_profile.salary_currency))
        if getattr(candidate_profile, "salary_period", None):
            salary_bits.append(f"per {candidate_profile.salary_period}")
        work_preferences.append(f"Salary expectation: {' '.join(salary_bits)}")

    return {
        "candidate_name": getattr(candidate_user, "display_name", None) or getattr(candidate_user, "username", None) or "Candidate",
        "vacancy_role_title": getattr(vacancy, "role_title", None),
        "candidate_summary_text": approval_summary,
        "skills": skills[:12],
        "work_preferences": work_preferences,
        "verification_status": "verification_submitted" if verification is not None else "verification_not_found",
        "interview_summary": (evaluation or {}).get("interview_summary"),
        "strengths": _clean_list((evaluation or {}).get("strengths")),
        "risks": _clean_list((evaluation or {}).get("risks")),
        "recommendation": (evaluation or {}).get("recommendation"),
        "final_score": (evaluation or {}).get("final_score"),
    }


def build_vacancy_package(
    *,
    vacancy,
    vacancy_summary: dict | None,
) -> dict:
    summary = vacancy_summary or {}
    approval_summary = summary.get("approval_summary_text")
    stack = _clean_list(getattr(vacancy, "primary_tech_stack_json", None) or summary.get("primary_tech_stack_json"))

    work_details = []
    if getattr(vacancy, "seniority_normalized", None):
        work_details.append(f"Seniority: {vacancy.seniority_normalized}")
    if getattr(vacancy, "work_format", None):
        work_details.append(f"Work format: {vacancy.work_format}")
    countries = _clean_list(getattr(vacancy, "countries_allowed_json", None))
    if countries:
        work_details.append(f"Countries: {', '.join(countries[:8])}")
    if getattr(vacancy, "budget_min", None) is not None or getattr(vacancy, "budget_max", None) is not None:
        budget_min = getattr(vacancy, "budget_min", None)
        budget_max = getattr(vacancy, "budget_max", None)
        if budget_min is not None and budget_max is not None:
            amount = f"{budget_min:.0f}-{budget_max:.0f}"
        else:
            amount = f"{(budget_min if budget_min is not None else budget_max):.0f}"
        if getattr(vacancy, "budget_currency", None):
            amount = f"{amount} {vacancy.budget_currency}"
        if getattr(vacancy, "budget_period", None):
            amount = f"{amount} per {vacancy.budget_period}"
        work_details.append(f"Budget: {amount}")

    project_description = getattr(vacancy, "project_description", None) or summary.get("project_description_excerpt")

    return {
        "vacancy_role_title": getattr(vacancy, "role_title", None) or "Open role",
        "vacancy_summary_text": approval_summary,
        "stack": stack[:12],
        "work_details": work_details,
        "project_description": project_description,
    }
