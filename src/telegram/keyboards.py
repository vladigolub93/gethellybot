from __future__ import annotations


def contact_request_keyboard() -> dict:
    return {
        "keyboard": [
            [
                {
                    "text": "Share Contact",
                    "request_contact": True,
                }
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def consent_keyboard() -> dict:
    return {
        "keyboard": [["I agree"]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def role_selection_keyboard() -> dict:
    return {
        "keyboard": [["Candidate", "Hiring Manager"]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def summary_review_keyboard(*, edit_allowed: bool = True) -> dict:
    keyboard = [["Approve summary"]]
    if edit_allowed:
        keyboard.append(["Change summary"])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def interview_invitation_keyboard() -> dict:
    return {
        "keyboard": [["Accept interview", "Skip opportunity"]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def manager_review_keyboard() -> dict:
    return {
        "keyboard": [["Approve candidate", "Reject candidate"]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def deletion_confirmation_keyboard(entity_type: str) -> dict:
    confirm_text = "Confirm delete profile" if entity_type == "candidate" else "Confirm delete vacancy"
    return {
        "keyboard": [[confirm_text], ["Cancel delete"]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def remove_keyboard() -> dict:
    return {"remove_keyboard": True}
