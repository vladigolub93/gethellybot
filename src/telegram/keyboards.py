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


def manager_review_keyboard() -> dict:
    return {
        "keyboard": [["Approve candidate", "Reject candidate"]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }

def manager_pre_interview_inline_keyboard(*, match_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Interview",
                    "callback_data": f"mgr_pre:int:{match_id}",
                },
                {
                    "text": "Skip",
                    "callback_data": f"mgr_pre:skip:{match_id}",
                },
            ]
        ]
    }


def candidate_vacancy_inline_keyboard(*, match_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Apply",
                    "callback_data": f"cand_pre:apply:{match_id}",
                },
                {
                    "text": "Skip",
                    "callback_data": f"cand_pre:skip:{match_id}",
                },
            ]
        ]
    }


def interview_invitation_inline_keyboard(*, match_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Accept interview",
                    "callback_data": f"cand_inv:accept:{match_id}",
                },
                {
                    "text": "Skip opportunity",
                    "callback_data": f"cand_inv:skip:{match_id}",
                },
            ]
        ]
    }


def candidate_cv_challenge_keyboard(url: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Play CV Challenge",
                    "web_app": {"url": url},
                }
            ]
        ]
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
