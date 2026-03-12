from __future__ import annotations

QUESTION_KEYS = (
    "salary",
    "work_format",
    "location",
    "english_level",
    "preferred_domains",
    "assessment_preferences",
)


QUESTION_LABELS = {
    "salary": "salary expectations",
    "work_format": "preferred work format",
    "location": "current location",
    "english_level": "English level",
    "preferred_domains": "project or domain preferences",
    "assessment_preferences": "assessment preferences",
}


def initial_questions_prompt() -> str:
    return question_prompt("salary")


def question_prompt(question_key: str, *, work_format: str | None = None) -> str:
    prompts = {
        "salary": "Nice. First, what are your salary expectations?",
        "work_format": "And one more thing: are you looking only for remote, or also hybrid / office?",
        "location": (
            "Got it. Now tell me your current city and country."
            if work_format in {"office", "hybrid"}
            else "Got it. Now tell me your current country. If you want, you can add city too."
        ),
        "english_level": "What is your English level right now? For example: B1, B2, or C1.",
        "preferred_domains": "Do you have any project or domain preferences? For example fintech, AI/ML, SaaS. If not, just say any.",
        "assessment_preferences": "Last one: should I show roles with take-home tasks and live coding? Say yes or no for both.",
    }
    return prompts[question_key]


def follow_up_prompt(question_key: str, *, work_format: str | None = None) -> str:
    prompts = {
        "salary": "Quick уточнение: share the amount, currency, and period for your salary expectations.",
        "work_format": "Quick уточнение: tell me if you want remote, hybrid, or office.",
        "location": (
            "Quick уточнение: for office or hybrid roles I need your current city and country."
            if work_format in {"office", "hybrid"}
            else "Quick уточнение: share your current country. You can add city too."
        ),
        "english_level": "Quick уточнение: share your English level in a simple format like B1, B2, or C1.",
        "preferred_domains": "Quick уточнение: name the domains you prefer, or say any if you have no preference.",
        "assessment_preferences": "Quick уточнение: tell me if I should show roles with take-home tasks and with live coding.",
    }
    return prompts[question_key]


def missing_questions_prompt(missing_keys, *, work_format: str | None = None) -> str:
    if not missing_keys:
        return "I have everything I need here."
    return question_prompt(missing_keys[0], work_format=work_format)
