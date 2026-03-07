def build_question_plan(*, vacancy, candidate_summary: dict) -> list[str]:
    role_title = vacancy.role_title or "this role"
    tech_stack = vacancy.primary_tech_stack_json or []
    primary_stack = ", ".join(tech_stack[:3]) if tech_stack else "your main stack"
    years_experience = candidate_summary.get("years_experience")
    years_context = (
        f"given your {years_experience} years of experience"
        if years_experience is not None
        else "given your background"
    )
    return [
        f"Tell me about your most relevant experience for {role_title}.",
        f"Describe a recent project where you used {primary_stack}.",
        f"What was the most technically difficult problem you solved {years_context}?",
        "How do you approach delivery tradeoffs and communication inside a team?",
        f"Why are you a strong fit for this vacancy and what risks should we know about?",
    ]
