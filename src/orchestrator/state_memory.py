from __future__ import annotations

from typing import Any

from src.matching.filters import evaluate_hard_filters
from src.shared.hiring_taxonomy import display_domains, display_english_level, display_hiring_stages


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


_CANDIDATE_BLOCKER_LABELS = {
    "location_mismatch": "your location is outside the allowed countries on many open roles",
    "work_format_mismatch": "many open roles use a different work format",
    "office_city_mismatch": "office or hybrid roles often need a specific city",
    "salary_above_budget": "your salary floor is above many vacancy budgets",
    "seniority_mismatch": "many roles are calibrated for a higher seniority",
    "english_level_mismatch": "many roles require a higher English level",
    "take_home_preference_mismatch": "some roles include take-home tasks that you asked to hide",
    "live_coding_preference_mismatch": "some roles include live coding that you asked to hide",
}

_MANAGER_BLOCKER_LABELS = {
    "location_mismatch": "many ready candidates are outside the allowed countries",
    "work_format_mismatch": "many ready candidates prefer a different work format",
    "office_city_mismatch": "office or hybrid city requirements are too narrow for many ready candidates",
    "salary_above_budget": "candidate salary floors are above the current budget",
    "seniority_mismatch": "many ready candidates are below the target seniority",
    "english_level_mismatch": "the English requirement is too high for many ready candidates",
    "take_home_preference_mismatch": "some candidates hide take-home roles",
    "live_coding_preference_mismatch": "some candidates hide live-coding roles",
}


def _top_matching_blockers(reason_counts: dict[str, int], *, labels: dict[str, str], limit: int = 2) -> list[str]:
    ranked = sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    results: list[str] = []
    for reason, _count in ranked:
        label = labels.get(reason)
        if label and label not in results:
            results.append(label)
        if len(results) >= limit:
            break
    return results


def _join_reasons(reasons: list[str]) -> str:
    if not reasons:
        return ""
    if len(reasons) == 1:
        return reasons[0]
    return f"{', '.join(reasons[:-1])}, and {reasons[-1]}"


def _candidate_matching_blockers_memory(*, stage: str | None, candidate, vacancies) -> list[str]:
    if candidate is None or stage != "READY":
        return []

    open_vacancies = _call_optional(vacancies, "get_open_vacancies") or []
    if not open_vacancies:
        return ["Matching blocker snapshot: there are no open roles right now."]

    pass_count = 0
    reason_counts: dict[str, int] = {}
    for vacancy in open_vacancies:
        reasons = evaluate_hard_filters(candidate, vacancy)
        if not reasons:
            pass_count += 1
            continue
        for reason in set(reasons):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    snippets: list[str] = []
    if pass_count:
        snippets.append(
            f"Matching blocker snapshot: {pass_count} open roles currently pass your hard filters, so the main constraint is stronger fit on stack, role, or domain rather than a hard blocker."
        )
    if reason_counts:
        blockers = _top_matching_blockers(reason_counts, labels=_CANDIDATE_BLOCKER_LABELS)
        if blockers:
            snippets.append(
                f"Current matching blockers: across {len(open_vacancies)} open roles, the biggest blockers right now are {_join_reasons(blockers)}."
            )
    return snippets


def _manager_matching_blockers_memory(*, stage: str | None, vacancy, candidates) -> list[str]:
    if vacancy is None or stage != "OPEN":
        return []

    ready_candidates = _call_optional(candidates, "get_ready_profiles") or []
    if not ready_candidates:
        return ["Matching blocker snapshot: there are no ready candidates in the pool right now."]

    pass_count = 0
    reason_counts: dict[str, int] = {}
    for candidate in ready_candidates:
        reasons = evaluate_hard_filters(candidate, vacancy)
        if not reasons:
            pass_count += 1
            continue
        for reason in set(reasons):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    snippets: list[str] = []
    if pass_count:
        snippets.append(
            f"Matching blocker snapshot: {pass_count} ready candidates currently pass hard filters for this vacancy, so Helly is mainly waiting for stronger fit on stack, role, or domain before sending profiles."
        )
    if reason_counts:
        blockers = _top_matching_blockers(reason_counts, labels=_MANAGER_BLOCKER_LABELS)
        if blockers:
            snippets.append(
                f"Current matching blockers: across {len(ready_candidates)} ready candidates, the biggest blockers right now are {_join_reasons(blockers)}."
            )
    return snippets


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
    english_level = display_english_level(getattr(candidate, "english_level", None))
    if english_level:
        parts.append(f"english {english_level}")
    preferred_domains = display_domains(getattr(candidate, "preferred_domains_json", None))
    if preferred_domains:
        parts.append(f"preferred domains {', '.join(preferred_domains)}")
    show_take_home = getattr(candidate, "show_take_home_task_roles", None)
    if show_take_home is not None:
        parts.append("take-home roles shown" if show_take_home else "take-home roles hidden")
    show_live_coding = getattr(candidate, "show_live_coding_roles", None)
    if show_live_coding is not None:
        parts.append("live-coding roles shown" if show_live_coding else "live-coding roles hidden")
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


def _candidate_feedback_line(candidate) -> str | None:
    if candidate is None:
        return None
    current = dict(getattr(candidate, "questions_context_json", None) or {})
    matching_feedback = dict(current.get("matching_feedback") or {})
    events = list(matching_feedback.get("candidate_feedback_events") or [])
    if not events:
        return None
    recent_texts = []
    for item in events[-2:]:
        text = _truncate(item.get("text"), limit=120)
        if text:
            recent_texts.append(text)
    if not recent_texts:
        return None
    return "Recent candidate mismatch feedback: " + " | ".join(recent_texts)


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
    office_city = getattr(vacancy, "office_city", None)
    if office_city:
        parts.append(f"office city {office_city}")
    countries = _clean_list(getattr(vacancy, "countries_allowed_json", None), limit=6)
    if countries:
        parts.append(f"countries {', '.join(countries)}")
    required_english = display_english_level(getattr(vacancy, "required_english_level", None))
    if required_english:
        parts.append(f"required english {required_english}")
    has_take_home = getattr(vacancy, "has_take_home_task", None)
    if has_take_home is True:
        take_home_text = "take-home included"
        if getattr(vacancy, "take_home_paid", None) is True:
            take_home_text = "paid take-home included"
        elif getattr(vacancy, "take_home_paid", None) is False:
            take_home_text = "unpaid take-home included"
        parts.append(take_home_text)
    elif has_take_home is False:
        parts.append("no take-home task")
    has_live_coding = getattr(vacancy, "has_live_coding", None)
    if has_live_coding is True:
        parts.append("live coding included")
    elif has_live_coding is False:
        parts.append("no live coding")
    hiring_stages = display_hiring_stages(getattr(vacancy, "hiring_stages_json", None))
    if hiring_stages:
        parts.append(f"hiring stages {', '.join(hiring_stages)}")
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


def _vacancy_feedback_line(vacancy) -> str | None:
    if vacancy is None:
        return None
    current = dict(getattr(vacancy, "questions_context_json", None) or {})
    matching_feedback = dict(current.get("matching_feedback") or {})
    events = list(matching_feedback.get("manager_feedback_events") or [])
    if not events:
        return None
    recent_texts = []
    for item in events[-2:]:
        text = _truncate(item.get("text"), limit=120)
        if text:
            recent_texts.append(text)
    if not recent_texts:
        return None
    return "Recent manager feedback on candidate flow: " + " | ".join(recent_texts)


def _evaluation_memory(evaluation) -> list[str]:
    if evaluation is None:
        return []
    report = getattr(evaluation, "report_json", None) or {}
    snippets: list[str] = []
    interview_summary = _truncate(report.get("interview_summary"), limit=260)
    if interview_summary:
        snippets.append(f"Saved interview summary: {interview_summary}")
    strengths = _clean_list(report.get("strengths") or getattr(evaluation, "strengths_json", None), limit=4)
    if strengths:
        snippets.append("Saved evaluation strengths: " + "; ".join(str(item) for item in strengths))
    risks = _clean_list(report.get("risks") or getattr(evaluation, "risks_json", None), limit=4)
    if risks:
        snippets.append("Saved evaluation risks: " + "; ".join(str(item) for item in risks))
    recommendation = report.get("recommendation")
    if recommendation is None:
        recommendation = getattr(evaluation, "recommendation", None)
    final_score = report.get("final_score")
    if final_score is None:
        final_score = getattr(evaluation, "final_score", None)
    if recommendation or final_score is not None:
        parts = []
        if recommendation:
            parts.append(f"recommendation {recommendation}")
        if final_score is not None:
            parts.append(f"final score {final_score}")
        snippets.append("Saved evaluation outcome: " + "; ".join(parts) + ".")
    return snippets


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


def _candidate_cv_challenge_memory(*, stage: str | None, candidate, version, matches, cv_challenges) -> list[str]:
    if candidate is None or stage != "READY":
        return []

    summary = getattr(version, "summary_json", None) or {}
    saved_skills = _clean_list(summary.get("skills"), limit=20)
    active_matches = _call_optional(matches, "list_active_for_candidate", candidate.id) or []
    snippets: list[str] = []

    if not active_matches and len(saved_skills) >= 3:
        snippets.append(
            "Saved waiting-state fact: there are no live opportunities right now and Helly CV Challenge is available in the WebApp dashboard while the candidate waits for matches."
        )

    active_attempt = _call_optional(cv_challenges, "get_latest_active_for_candidate_profile", candidate.id)
    if active_attempt is not None and getattr(active_attempt, "finished_at", None) is None:
        progress = getattr(active_attempt, "result_json", None) or {}
        if progress:
            parts = [
                f"score {int(getattr(active_attempt, 'score', 0) or 0)}",
                f"stage reached {int(getattr(active_attempt, 'stage_reached', 1) or 1)}",
                f"lives left {int(getattr(active_attempt, 'lives_left', 0) or 0)}",
            ]
            snippets.append(
                "Saved CV Challenge run in progress: "
                + "; ".join(parts)
                + ". The candidate can resume it in the WebApp dashboard."
            )

    completed_attempt = _call_optional(cv_challenges, "get_latest_completed_for_candidate_profile", candidate.id)
    if completed_attempt is not None:
        status_text = "won" if bool(getattr(completed_attempt, "won", False)) else "lost"
        parts = [
            f"last run {status_text}",
            f"score {int(getattr(completed_attempt, 'score', 0) or 0)}",
            f"stage reached {int(getattr(completed_attempt, 'stage_reached', 1) or 1)}",
        ]
        result = getattr(completed_attempt, "result_json", None) or {}
        total_mistakes = result.get("totalMistakes")
        if total_mistakes is not None:
            parts.append(f"mistakes {int(total_mistakes)}")
        snippets.append("Saved CV Challenge result: " + "; ".join(parts) + ".")
        missed_skills = _clean_list(result.get("missedSkills"), limit=6)
        if missed_skills:
            snippets.append("Saved CV Challenge missed skills: " + "; ".join(missed_skills) + ".")

    return _dedupe(snippets)


def _candidate_memory(*, user_id, stage: str | None, candidates, matches, vacancies, interviews, cv_challenges) -> list[str]:
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
    feedback_line = _candidate_feedback_line(candidate)
    if feedback_line and stage in {"READY", "VACANCY_REVIEW"}:
        snippets.append(feedback_line)

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
        invited_matches = _call_optional(matches, "list_invited_for_candidate", candidate.id, limit=3)
        if invited_matches:
            vacancy_briefs = []
            for index, match in enumerate(invited_matches, start=1):
                vacancy = _call_optional(vacancies, "get_by_id", getattr(match, "vacancy_id", None))
                if vacancy is None:
                    continue
                brief = _format_vacancy_brief(slot=index, vacancy=vacancy)
                if brief:
                    vacancy_briefs.append(brief)
            if vacancy_briefs:
                snippets.append("Current interview invitations: " + " | ".join(vacancy_briefs))
            if len(invited_matches) == 1:
                current_vacancy = _call_optional(vacancies, "get_by_id", getattr(invited_matches[0], "vacancy_id", None))
        else:
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

    snippets.extend(
        _candidate_cv_challenge_memory(
            stage=stage,
            candidate=candidate,
            version=version,
            matches=matches,
            cv_challenges=cv_challenges,
        )
    )
    snippets.extend(
        _candidate_matching_blockers_memory(
            stage=stage,
            candidate=candidate,
            vacancies=vacancies,
        )
    )

    return _dedupe(snippets)


def _manager_memory(*, user_id, stage: str | None, candidates, matches, vacancies, evaluations) -> list[str]:
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
    feedback_line = _vacancy_feedback_line(vacancy)
    if feedback_line and stage in {"OPEN", "PRE_INTERVIEW_REVIEW"}:
        snippets.append(feedback_line)

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
        review_vacancy_ids = [item.id for item in open_vacancies] or [vacancy.id]
        review_matches = _call_optional(matches, "list_manager_review_for_manager", review_vacancy_ids, limit=3)
        if review_matches:
            candidate_briefs = []
            for index, review_match in enumerate(review_matches, start=1):
                candidate = _call_optional(candidates, "get_by_id", getattr(review_match, "candidate_profile_id", None))
                version = _get_current_version(candidates, candidate)
                brief = _format_candidate_brief(slot=index, candidate=candidate, version=version)
                if brief:
                    candidate_briefs.append(brief)
            if candidate_briefs:
                snippets.append("Current candidates under final manager review: " + " | ".join(candidate_briefs))
            if len(review_matches) == 1:
                evaluation = _call_optional(evaluations, "get_by_match_id", getattr(review_matches[0], "id", None))
                snippets.extend(_evaluation_memory(evaluation))
        else:
            review_match = _call_optional(matches, "get_latest_manager_review_for_manager", review_vacancy_ids)
            if review_match is not None:
                candidate = _call_optional(candidates, "get_by_id", getattr(review_match, "candidate_profile_id", None))
                version = _get_current_version(candidates, candidate)
                brief = _format_candidate_brief(slot=1, candidate=candidate, version=version)
                if brief:
                    snippets.append(
                        "Current candidate under final manager review: "
                        + _strip_slot_prefix(brief).strip()
                    )
                evaluation = _call_optional(evaluations, "get_by_match_id", getattr(review_match, "id", None))
                snippets.extend(_evaluation_memory(evaluation))

    snippets.extend(
        _manager_matching_blockers_memory(
            stage=stage,
            vacancy=vacancy,
            candidates=candidates,
        )
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
    evaluations,
    cv_challenges,
) -> list[str]:
    if role == "candidate":
        return _candidate_memory(
            user_id=user_id,
            stage=stage,
            candidates=candidates,
            matches=matches,
            vacancies=vacancies,
            interviews=interviews,
            cv_challenges=cv_challenges,
        )
    if role == "hiring_manager":
        return _manager_memory(
            user_id=user_id,
            stage=stage,
            candidates=candidates,
            matches=matches,
            vacancies=vacancies,
            evaluations=evaluations,
        )
    return []
