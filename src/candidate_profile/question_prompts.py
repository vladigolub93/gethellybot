QUESTION_KEYS = ("salary", "location", "work_format")


QUESTION_LABELS = {
    "salary": "salary expectations",
    "location": "current location",
    "work_format": "preferred work format",
}


def initial_questions_prompt() -> str:
    return (
        "Nice. Now send me three quick things: your salary expectations, current location, "
        "and preferred work setup (remote, hybrid, or office). One message is perfect."
    )


def follow_up_prompt(question_key: str) -> str:
    prompts = {
        "salary": "Quick уточнение: share the amount, currency, and period for your salary expectations.",
        "location": "Quick уточнение: share your current city and country.",
        "work_format": "Quick уточнение: tell me if you want remote, hybrid, or office.",
    }
    return prompts[question_key]


def missing_questions_prompt(missing_keys) -> str:
    labels = [QUESTION_LABELS[key] for key in missing_keys]
    return f"Still missing: {', '.join(labels)}."
