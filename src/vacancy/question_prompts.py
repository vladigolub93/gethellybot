QUESTION_KEYS = (
    "budget",
    "countries",
    "work_format",
    "team_size",
    "project_description",
    "primary_tech_stack",
)


QUESTION_LABELS = {
    "budget": "budget range",
    "countries": "countries allowed for hiring",
    "work_format": "work format",
    "team_size": "team size",
    "project_description": "project description",
    "primary_tech_stack": "primary tech stack",
}


def initial_clarification_prompt() -> str:
    return (
        "Send the vacancy clarifications: budget range, countries allowed for hiring, "
        "work format, team size, project description, and primary tech stack."
    )


def follow_up_prompt(question_key: str) -> str:
    prompts = {
        "budget": "Please clarify the budget range with amount, currency, and period.",
        "countries": "Please clarify which countries are allowed for hiring.",
        "work_format": "Please clarify the work format: remote, hybrid, or office.",
        "team_size": "Please clarify the team size.",
        "project_description": "Please clarify the project description in one or two sentences.",
        "primary_tech_stack": "Please clarify the primary tech stack.",
    }
    return prompts[question_key]


def missing_questions_prompt(missing_keys) -> str:
    labels = [QUESTION_LABELS[key] for key in missing_keys]
    return f"Still missing: {', '.join(labels)}."
