def build_interview_summary(answer_texts: list[str]) -> str:
    return " ".join(answer_texts).strip()


def evaluate_candidate(*, candidate_summary: dict, vacancy, answer_texts: list[str]) -> dict:
    skills = set(candidate_summary.get("skills") or [])
    vacancy_skills = set(vacancy.primary_tech_stack_json or [])
    overlap = len(skills & vacancy_skills)
    required = len(vacancy_skills) or 1
    skill_ratio = overlap / required
    answer_count = len([answer for answer in answer_texts if answer and answer.strip()])
    answer_score = min(answer_count / 5.0, 1.0)
    score = round((skill_ratio * 0.6) + (answer_score * 0.4), 4)

    strengths = []
    risks = []
    if overlap:
        strengths.append("Relevant tech stack overlap.")
    if candidate_summary.get("years_experience"):
        strengths.append("Candidate has stated prior relevant experience.")
    if answer_count < 5:
        risks.append("Interview coverage is incomplete or sparse.")
    if skill_ratio < 0.5:
        risks.append("Core stack overlap is limited.")

    recommendation = "advance" if score >= 0.65 else "reject"
    return {
        "final_score": score,
        "strengths": strengths,
        "risks": risks,
        "recommendation": recommendation,
        "interview_summary": build_interview_summary(answer_texts)[:1500],
    }
