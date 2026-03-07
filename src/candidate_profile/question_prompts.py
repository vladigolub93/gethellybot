QUESTION_KEYS = ("salary", "location", "work_format")


QUESTION_LABELS = {
    "salary": "salary expectations",
    "location": "current location",
    "work_format": "preferred work format",
}


def initial_questions_prompt() -> str:
    return (
        "Summary approved. Send your salary expectations, current location, and preferred "
        "work format (remote, hybrid, or office). You can answer in one message or separately."
    )


def follow_up_prompt(question_key: str) -> str:
    prompts = {
        "salary": "Please clarify your salary expectations with amount, currency, and period.",
        "location": "Please clarify your current location with city and country.",
        "work_format": "Please clarify your preferred work format: remote, hybrid, or office.",
    }
    return prompts[question_key]


def missing_questions_prompt(missing_keys) -> str:
    labels = [QUESTION_LABELS[key] for key in missing_keys]
    return f"Still missing: {', '.join(labels)}."
