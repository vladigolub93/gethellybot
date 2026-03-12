from __future__ import annotations

QUESTION_KEYS = (
    "budget",
    "work_format",
    "office_city",
    "countries",
    "english_level",
    "assessment",
    "take_home_paid",
    "hiring_stages",
    "team_size",
    "project_description",
    "primary_tech_stack",
)


QUESTION_LABELS = {
    "budget": "budget range",
    "work_format": "work format",
    "office_city": "office or hybrid city",
    "countries": "countries allowed for hiring",
    "english_level": "required English level",
    "assessment": "assessment steps",
    "take_home_paid": "take-home compensation",
    "hiring_stages": "hiring stages",
    "team_size": "team size",
    "project_description": "project description",
    "primary_tech_stack": "primary tech stack",
}


def initial_clarification_prompt() -> str:
    return question_prompt("budget")


def question_prompt(
    question_key: str,
    *,
    work_format: str | None = None,
    has_take_home_task: bool | None = None,
) -> str:
    prompts = {
        "budget": "Nice. First, what budget are you hiring with for this role?",
        "work_format": "Got it. Is this remote, office, or hybrid?",
        "office_city": "For office or hybrid hiring, what city should the candidate be based in?",
        "countries": "Which countries are you open to hiring from?",
        "english_level": "What English level does the candidate need here? For example: B1, B2, or C1.",
        "assessment": "Will this hiring process include a take-home task, live coding, both, or neither?",
        "take_home_paid": "If there is a take-home task, will it be paid or unpaid?",
        "hiring_stages": "What hiring stages will the candidate go through? For example recruiter screen, manager call, technical interview, final.",
        "team_size": "What is the size of the team this person would join?",
        "project_description": "What is the project about? One or two clear sentences is enough.",
        "primary_tech_stack": "And what is the main stack? What should I prioritize first when matching?",
    }
    if question_key == "countries" and work_format in {"office", "hybrid"}:
        prompts["countries"] = "Which countries are you open to hiring from for this office or hybrid role?"
    if question_key == "take_home_paid" and has_take_home_task is False:
        prompts["take_home_paid"] = "There is no take-home task here, so we can skip this."
    return prompts[question_key]


def follow_up_prompt(
    question_key: str,
    *,
    work_format: str | None = None,
    has_take_home_task: bool | None = None,
) -> str:
    prompts = {
        "budget": "Please clarify the budget range with amount, currency, and period.",
        "work_format": "Please clarify the work format: remote, hybrid, or office.",
        "office_city": "Please clarify the office or hybrid city for this role.",
        "countries": "Please clarify which countries are allowed for hiring.",
        "english_level": "Please clarify the required English level in a simple format like B1, B2, or C1.",
        "assessment": "Please clarify whether this process includes a take-home task, live coding, both, or neither.",
        "take_home_paid": "Please clarify whether the take-home task is paid or unpaid.",
        "hiring_stages": "Please clarify the hiring stages candidates should expect.",
        "team_size": "Please clarify the team size.",
        "project_description": "Please clarify the project description in one or two sentences.",
        "primary_tech_stack": "Please clarify the primary tech stack.",
    }
    if question_key == "countries" and work_format in {"office", "hybrid"}:
        prompts["countries"] = "Please clarify which countries are allowed for this office or hybrid role."
    if question_key == "take_home_paid" and has_take_home_task is False:
        prompts["take_home_paid"] = "No payment detail is needed because there is no take-home task."
    return prompts[question_key]


def missing_questions_prompt(
    missing_keys,
    *,
    work_format: str | None = None,
    has_take_home_task: bool | None = None,
) -> str:
    if not missing_keys:
        return "I have the basics I need."
    return question_prompt(
        missing_keys[0],
        work_format=work_format,
        has_take_home_task=has_take_home_task,
    )
