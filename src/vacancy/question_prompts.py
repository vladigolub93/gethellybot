QUESTION_KEYS = (
    "budget",
    "work_format",
    "countries",
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
    return question_prompt("budget")


def question_prompt(question_key: str) -> str:
    prompts = {
        "budget": "Nice. First, what budget are you hiring with for this role?",
        "work_format": "Got it. Is this remote, office, or hybrid?",
        "countries": "Which countries are you open to hiring from?",
        "team_size": "What is the size of the team this person would join?",
        "project_description": "What is the project about? One or two clear sentences is enough.",
        "primary_tech_stack": "And what is the main stack? What should I prioritize first when matching?",
    }
    return prompts[question_key]


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
    if not missing_keys:
        return "I have the basics I need."
    return question_prompt(missing_keys[0])
