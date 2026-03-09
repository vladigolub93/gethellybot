QUESTION_KEYS = ("salary", "location", "work_format")


QUESTION_LABELS = {
    "salary": "salary expectations",
    "location": "current location",
    "work_format": "preferred work format",
}


def initial_questions_prompt() -> str:
    return question_prompt("salary")


def question_prompt(question_key: str) -> str:
    prompts = {
        "salary": "Nice. First, what are your salary expectations?",
        "location": "Got it. Now tell me your current location.",
        "work_format": "And one more thing: are you looking only for remote, or also hybrid / office?",
    }
    return prompts[question_key]


def follow_up_prompt(question_key: str) -> str:
    prompts = {
        "salary": "Quick уточнение: share the amount, currency, and period for your salary expectations.",
        "location": "Quick уточнение: share your current city and country.",
        "work_format": "Quick уточнение: tell me if you want remote, hybrid, or office.",
    }
    return prompts[question_key]


def missing_questions_prompt(missing_keys) -> str:
    if not missing_keys:
        return "I have everything I need here."
    return question_prompt(missing_keys[0])
