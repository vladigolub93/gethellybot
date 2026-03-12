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
        "salary": "Let’s lock in your preferences. What salary range would feel right for your next role?",
        "work_format": "What work setup are you open to: remote only, or also hybrid / office?",
        "location": (
            "Thanks. For office or hybrid roles I need your current city and country."
            if work_format in {"office", "hybrid"}
            else "Thanks. What country are you currently based in? You can add your city too if you want."
        ),
        "english_level": "What English level would you be comfortable interviewing and working in? For example: B1, B2, or C1.",
        "preferred_domains": "Do you have any product or domain preferences? For example fintech, AI/ML, SaaS. If you’re open to anything, just say any.",
        "assessment_preferences": "Last one: should I include roles with take-home tasks or live coding? You can answer yes or no for each.",
    }
    return prompts[question_key]


def follow_up_prompt(question_key: str, *, work_format: str | None = None) -> str:
    prompts = {
        "salary": "Quick clarification: share the amount, currency, and period for your salary expectations.",
        "work_format": "Quick clarification: tell me if you want remote, hybrid, or office.",
        "location": (
            "Quick clarification: for office or hybrid roles I need your current city and country."
            if work_format in {"office", "hybrid"}
            else "Quick clarification: share your current country. You can add city too."
        ),
        "english_level": "Quick clarification: share your English level in a simple format like B1, B2, or C1.",
        "preferred_domains": "Quick clarification: name the domains you prefer, or say any if you have no preference.",
        "assessment_preferences": "Quick clarification: tell me if I should show roles with take-home tasks and with live coding.",
    }
    return prompts[question_key]


def missing_questions_prompt(missing_keys, *, work_format: str | None = None) -> str:
    if not missing_keys:
        return "I have everything I need here."
    return question_prompt(missing_keys[0], work_format=work_format)
