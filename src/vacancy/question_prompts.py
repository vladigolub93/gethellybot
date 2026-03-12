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
        "budget": "Let’s lock in the basics. What budget range are you hiring with for this role?",
        "work_format": "What work setup is this role: remote, office, or hybrid?",
        "office_city": "If it is office or hybrid, which city should the candidate be based in?",
        "countries": "Which countries are you open to hiring from for this role?",
        "english_level": "What English level does the candidate need to do this role well? For example: B1, B2, or C1.",
        "assessment": "Will this hiring process include a take-home task, live coding, both, or neither?",
        "take_home_paid": "If there is a take-home task, will it be paid or unpaid?",
        "hiring_stages": "What hiring stages should the candidate expect? A short list is enough, for example recruiter screen, manager call, technical interview, final.",
        "team_size": "What team would this person join? A rough size is enough.",
        "project_description": "What is the project about? One or two clear sentences is enough.",
        "primary_tech_stack": "What is the main stack for this role? Tell me the technologies I should prioritize in matching.",
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
        "budget": "Quick clarification: share the budget range with amount, currency, and period.",
        "work_format": "Quick clarification: tell me if the role is remote, hybrid, or office.",
        "office_city": "Quick clarification: which office or hybrid city should I use for this role?",
        "countries": "Quick clarification: which countries are allowed for hiring here?",
        "english_level": "Quick clarification: share the required English level in a format like B1, B2, or C1.",
        "assessment": "Quick clarification: does this process include a take-home task, live coding, both, or neither?",
        "take_home_paid": "Quick clarification: is the take-home task paid or unpaid?",
        "hiring_stages": "Quick clarification: what hiring stages should candidates expect?",
        "team_size": "Quick clarification: what is the team size?",
        "project_description": "Quick clarification: describe the project in one or two sentences.",
        "primary_tech_stack": "Quick clarification: what is the primary tech stack?",
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
