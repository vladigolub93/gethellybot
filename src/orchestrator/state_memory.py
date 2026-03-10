from __future__ import annotations

from typing import Any


def _call_optional(target: Any, method_name: str, *args, **kwargs):
    method = getattr(target, method_name, None)
    if not callable(method):
        return None
    try:
        return method(*args, **kwargs)
    except Exception:
        return None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = " ".join(str(value or "").split()).strip()
        if text and text not in result:
            result.append(text)
    return result


def _truncate(value: str | None, *, limit: int = 220) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split()).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _clean_list(values, *, limit: int = 6) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = " ".join(str(value).split()).strip()
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _format_budget(vacancy) -> str | None:
    budget_min = getattr(vacancy, "budget_min", None)
    budget_max = getattr(vacancy, "budget_max", None)
    if budget_min is None and budget_max is None:
        return None
    if budget_min is not None and budget_max is not None:
        amount = f"{budget_min:.0f}-{budget_max:.0f}"
    else:
        amount = f"{(budget_min if budget_min is not None else budget_max):.0f}"
    currency = getattr(vacancy, "budget_currency", None)
    period = getattr(vacancy, "budget_period", None)
    if currency:
        amount = f"{amount} {currency}"
    if period:
        amount = f"{amount} per {period}"
    return amount


def _get_current_version(repo, entity):
    if entity is None:
        return None
    current = _call_optional(repo, "get_current_version", entity)
    if current is not None:
        return current
    version_id = getattr(entity, "current_version_id", None)
    if version_id is None:
        return None
    return _call_optional(repo, "get_version_by_id", version_id)


def _candidate_summary_text(version) -> str | None:
    if version is None:
        return None
    summary = getattr(version, "summary_json", None) or {}
    return summary.get("approval_summary_text") or summary.get("headline")


def _vacancy_summary_text(version) -> str | None:
    if version is None:
        return None
    summary = getattr(version, "summary_json", None) or {}
    return getattr(version, "approval_summary_text", None) or summary.get("approval_summary_text")


def _candidate_preferences_line(candidate) -> str | None:
    if candidate is None:
        return None
    parts: list[str] = []
    salary_min = getattr(candidate, "salary_min", None)
    if salary_min is not None:
        salary_text = f"{salary_min:.0f}"
        salary_currency = getattr(candidate, "salary_currency", None)
        salary_period = getattr(candidate, "salary_period", None)
        if salary_currency:
            salary_text = f"{salary_text} {salary_currency}"
        if salary_period:
            salary_text = f"{salary_text} per {salary_period}"
        parts.append(f"salary expectation {salary_text}")
    location_text = getattr(candidate, "location_text", None)
    if location_text:
        parts.append(f"location {location_text}")
    work_format = getattr(candidate, "work_format", None)
    if work_format:
        parts.append(f"work format {work_format}")
    if not parts:
        return None
    return f"Saved candidate preferences: {'; '.join(parts)}."


def _candidate_skills_line(version) -> str | None:
    if version is None:
        return None
    summary = getattr(version, "summary_json", None) or {}
    parts: list[str] = []
    years_experience = summary.get("years_experience")
    if years_experience is not None:
        parts.append(f"{years_experience}+ years experience")
    skills = _clean_list(summary.get("skills"), limit=8)
    if skills:
        parts.append(f"skills: {', '.join(skills)}")
    if not parts:
        return None
    return f"Saved candidate facts: {'; '.join(parts)}."


def _vacancy_details_line(vacancy) -> str | None:
    if vacancy is None:
        return None
    parts: list[str] = []
    role_title = getattr(vacancy, "role_title", None)
    if role_title:
        parts.append(f"role {role_title}")
    seniority = getattr(vacancy, "seniority_normalized", None)
    if seniority:
        parts.append(f"seniority {seniority}")
    budget = _format_budget(vacancy)
    if budget:
        parts.append(f"budget {budget}")
    work_format = getattr(vacancy, "work_format", None)
    if work_format:
        parts.append(f"work format {work_format}")
    countries = _clean_list(getattr(vacancy, "countries_allowed_json", None), limit=6)
    if countries:
        parts.append(f"countries {', '.join(countries)}")
    team_size = getattr(vacancy, "team_size", None)
    if team_size:
        parts.append(f"team size {team_size}")
    stack = _clean_list(getattr(vacancy, "primary_tech_stack_json", None), limit=8)
    if stack:
        parts.append(f"stack {', '.join(stack)}")
    if not parts:
        return None
    return f"Saved vacancy details: {'; '.join(parts)}."


def _vacancy_project_line(vacancy) -> str | None:
    project = _truncate(getattr(vacancy, "project_description", None), limit=240)
    if not project:
        return None
    return f"Saved project description: {project}"


def _format_candidate_brief(*, slot: int, candidate, version) -> str | None:
    summary = _candidate_summary_text(version)
    preferences = _candidate_preferences_line(candidate)
    parts = [f"{slot}."]
    if summary:
        parts.append(summary)
    if preferences:
        parts.append(preferences.removeprefix("Saved candidate preferences: ").rstrip("."))
    if len(parts) == 1:
        return None
    return " ".join(parts)


def _strip_slot_prefix(value: str) -> str:
    if ". " in value:
        return value.split(". ", 1)[1]
    return value


def _format_vacancy_brief(*, slot: int, vacancy) -> str | None:
    role_title = getattr(vacancy, "role_title", None) or "Open role"
    parts = [f"{slot}. {role_title}"]
    seniority = getattr(vacancy, "seniority_normalized", None)
    if seniority:
        parts.append(f"seniority {seniority}")
    budget = _format_budget(vacancy)
    if budget:
        parts.append(f"budget {budget}")
    work_format = getattr(vacancy, "work_format", None)
    if work_format:
        parts.append(f"work format {work_format}")
    return "; ".join(parts)


def _candidate_memory(*, user_id, stage: str | None, candidates, matches, vacancies, interviews) -> list[str]:
    candidate = _call_optional(candidates, "get_active_by_user_id", user_id)
    if candidate is None:
        return []

    version = _get_current_version(candidates, candidate)
    snippets: list[str] = []
    summary_text = _truncate(_candidate_summary_text(version), limit=260)
    if summary_text:
        snippets.append(f"Saved candidate summary: {summary_text}")
    preferences_line = _candidate_preferences_line(candidate)
    if preferences_line:
        snippets.append(preferences_line)
    skills_line = _candidate_skills_line(version)
    if skills_line:
        snippets.append(skills_line)

    if stage == "VACANCY_REVIEW":
        review_matches = _call_optional(
            matches,
            "list_pre_interview_review_for_candidate",
            candidate.id,
            limit=3,
        ) or []
        vacancy_briefs = []
        for index, match in enumerate(review_matches, start=1):
            vacancy = _call_optional(vacancies, "get_by_id", getattr(match, "vacancy_id", None))
            if vacancy is None:
                continue
            brief = _format_vacancy_brief(slot=index, vacancy=vacancy)
            if brief:
                vacancy_briefs.append(brief)
        if vacancy_briefs:
            snippets.append("Current matched vacancies in review: " + " | ".join(vacancy_briefs))

    current_vacancy = None
    if stage == "INTERVIEW_IN_PROGRESS":
        active_session = _call_optional(interviews, "get_active_session_for_candidate", candidate.id)
        if active_session is not None:
            current_vacancy = _call_optional(vacancies, "get_by_id", getattr(active_session, "vacancy_id", None))
    elif stage == "INTERVIEW_INVITED":
        invited_match = _call_optional(matches, "get_latest_invited_for_candidate", candidate.id)
        if invited_match is not None:
            current_vacancy = _call_optional(vacancies, "get_by_id", getattr(invited_match, "vacancy_id", None))
    if current_vacancy is not None:
        current_vacancy_brief = _format_vacancy_brief(slot=1, vacancy=current_vacancy)
        if current_vacancy_brief:
            snippets.append(
                "Current interview opportunity: "
                + _strip_slot_prefix(current_vacancy_brief).strip()
            )

    return _dedupe(snippets)


def _manager_memory(*, user_id, stage: str | None, candidates, matches, vacancies) -> list[str]:
    vacancy = _call_optional(vacancies, "get_latest_active_by_manager_user_id", user_id)
    if vacancy is None:
        vacancy = _call_optional(vacancies, "get_latest_incomplete_by_manager_user_id", user_id)
    if vacancy is None:
        open_vacancies = _call_optional(vacancies, "get_open_by_manager_user_id", user_id) or []
        vacancy = open_vacancies[0] if open_vacancies else None
    if vacancy is None:
        return []

    version = _get_current_version(vacancies, vacancy)
    snippets: list[str] = []
    summary_text = _truncate(_vacancy_summary_text(version), limit=260)
    if summary_text:
        snippets.append(f"Saved vacancy summary: {summary_text}")
    details_line = _vacancy_details_line(vacancy)
    if details_line:
        snippets.append(details_line)
    project_line = _vacancy_project_line(vacancy)
    if project_line:
        snippets.append(project_line)

    open_vacancies = _call_optional(vacancies, "get_open_by_manager_user_id", user_id) or []
    if len(open_vacancies) > 1:
        titles = [
            getattr(item, "role_title", None) or "Open role"
            for item in open_vacancies[:5]
        ]
        snippets.append("Open vacancies on this manager account: " + " | ".join(titles))

    if stage == "PRE_INTERVIEW_REVIEW":
        review_matches = _call_optional(
            matches,
            "list_pre_interview_review_for_vacancy",
            vacancy.id,
            limit=3,
        ) or []
        candidate_briefs = []
        for index, match in enumerate(review_matches, start=1):
            candidate = _call_optional(candidates, "get_by_id", getattr(match, "candidate_profile_id", None))
            version = _get_current_version(candidates, candidate)
            brief = _format_candidate_brief(slot=index, candidate=candidate, version=version)
            if brief:
                candidate_briefs.append(brief)
        if candidate_briefs:
            snippets.append("Current candidate batch in review: " + " | ".join(candidate_briefs))

    if stage == "MANAGER_REVIEW":
        review_match = _call_optional(matches, "get_latest_manager_review_for_manager", [vacancy.id])
        if review_match is not None:
            candidate = _call_optional(candidates, "get_by_id", getattr(review_match, "candidate_profile_id", None))
            version = _get_current_version(candidates, candidate)
            brief = _format_candidate_brief(slot=1, candidate=candidate, version=version)
            if brief:
                snippets.append(
                    "Current candidate under final manager review: "
                    + _strip_slot_prefix(brief).strip()
                )

    return _dedupe(snippets)


def build_state_memory(
    *,
    role: str | None,
    stage: str | None,
    user_id,
    candidates,
    vacancies,
    matches,
    interviews,
) -> list[str]:
    if role == "candidate":
        return _candidate_memory(
            user_id=user_id,
            stage=stage,
            candidates=candidates,
            matches=matches,
            vacancies=vacancies,
            interviews=interviews,
        )
    if role == "hiring_manager":
        return _manager_memory(
            user_id=user_id,
            stage=stage,
            candidates=candidates,
            matches=matches,
            vacancies=vacancies,
        )
    return []
