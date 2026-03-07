SENIORITY_ORDER = {
    "junior": 1,
    "middle": 2,
    "senior": 3,
}


def evaluate_hard_filters(candidate, vacancy) -> list[str]:
    reasons = []

    if vacancy.countries_allowed_json and candidate.country_code:
        if candidate.country_code not in vacancy.countries_allowed_json:
            reasons.append("location_mismatch")

    if vacancy.work_format and candidate.work_format:
        if vacancy.work_format != candidate.work_format:
            reasons.append("work_format_mismatch")

    if vacancy.budget_max is not None and candidate.salary_min is not None:
        if float(candidate.salary_min) > float(vacancy.budget_max):
            reasons.append("salary_above_budget")

    if vacancy.seniority_normalized and candidate.seniority_normalized:
        vacancy_level = SENIORITY_ORDER.get(vacancy.seniority_normalized)
        candidate_level = SENIORITY_ORDER.get(candidate.seniority_normalized)
        if vacancy_level is not None and candidate_level is not None and candidate_level < vacancy_level:
            reasons.append("seniority_mismatch")

    return reasons
