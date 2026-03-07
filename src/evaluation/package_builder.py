from __future__ import annotations


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
    if getattr(candidate_profile, "work_format", None):
        work_preferences.append(f"Work format: {candidate_profile.work_format}")
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

