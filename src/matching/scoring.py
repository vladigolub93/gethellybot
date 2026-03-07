from __future__ import annotations

def _as_set(values) -> set[str]:
    return {str(value).lower() for value in (values or []) if value}


def compute_embedding_score(candidate_skills, vacancy_skills) -> float:
    candidate_set = _as_set(candidate_skills)
    vacancy_set = _as_set(vacancy_skills)
    if not candidate_set or not vacancy_set:
        return 0.0
    intersection = len(candidate_set & vacancy_set)
    union = len(candidate_set | vacancy_set)
    return round(intersection / union, 4)


def compute_deterministic_score(
    *,
    candidate_skills,
    vacancy_skills,
    candidate_years_experience,
    vacancy_seniority,
    candidate_seniority,
) -> tuple[float, dict]:
    candidate_set = _as_set(candidate_skills)
    vacancy_set = _as_set(vacancy_skills)
    overlap = len(candidate_set & vacancy_set)
    required = len(vacancy_set) or 1
    skill_overlap_ratio = overlap / required

    experience_score = 0.0
    if candidate_years_experience is not None:
        experience_score = min(float(candidate_years_experience) / 10.0, 1.0)

    seniority_fit = 1.0 if candidate_seniority and candidate_seniority == vacancy_seniority else 0.5
    if not vacancy_seniority or not candidate_seniority:
        seniority_fit = 0.5

    total_score = round((skill_overlap_ratio * 0.6) + (experience_score * 0.2) + (seniority_fit * 0.2), 4)
    return total_score, {
        "skill_overlap_ratio": round(skill_overlap_ratio, 4),
        "experience_score": round(experience_score, 4),
        "seniority_fit": round(seniority_fit, 4),
    }
