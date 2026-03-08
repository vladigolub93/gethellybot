#!/usr/bin/env python3
from __future__ import annotations

import argparse

from scripts.inspect_telegram_user import load_snapshot


def _print(label: str, value) -> None:
    print(f"{label}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a compact smoke-test report for one Helly Telegram user"
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    args = parser.parse_args()

    snapshot = load_snapshot(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
    )

    if snapshot.user is None:
        print("status: not_found")
        return

    user = snapshot.user
    candidate = snapshot.candidate_profile or {}
    vacancy = snapshot.vacancy or {}
    interview = snapshot.interview_session or {}
    match = snapshot.invited_match or {}
    notification = snapshot.latest_notification or {}

    print("status: found")
    _print("user_id", user["id"])
    _print("telegram_user_id", user["telegram_user_id"])
    _print("telegram_chat_id", user["telegram_chat_id"])
    _print("display_name", user.get("display_name"))
    _print("roles", ",".join(
        role
        for role, enabled in (
            ("candidate", user.get("is_candidate")),
            ("hiring_manager", user.get("is_hiring_manager")),
        )
        if enabled
    ) or "none")

    _print("candidate_state", candidate.get("state"))
    _print("vacancy_state", vacancy.get("state"))
    _print("match_status", match.get("status"))
    _print("interview_state", interview.get("state"))
    _print("latest_notification", notification.get("template_key"))

    if snapshot.counts:
        counts = snapshot.counts
        _print(
            "counts",
            ", ".join(f"{key}={value}" for key, value in sorted(counts.items())),
        )

    next_checks: list[str] = []
    if candidate.get("state") == "CV_PENDING":
        next_checks.append("send CV text, document, or voice")
    elif candidate.get("state") == "SUMMARY_REVIEW":
        next_checks.append("approve or correct summary")
    elif candidate.get("state") == "QUESTIONS_PENDING":
        next_checks.append("send salary, location, and work format")
    elif candidate.get("state") == "VERIFICATION_PENDING":
        next_checks.append("send verification video")
    elif candidate.get("state") == "READY":
        next_checks.append("candidate is ready for matching")

    if vacancy.get("state") == "INTAKE_PENDING":
        next_checks.append("send job description")
    elif vacancy.get("state") == "CLARIFICATION_QA":
        next_checks.append("answer vacancy clarification questions")
    elif vacancy.get("state") == "OPEN":
        next_checks.append("vacancy is open for matching")

    if match.get("status") == "invited":
        next_checks.append("candidate can accept or skip interview")
    elif interview.get("state") == "IN_PROGRESS":
        next_checks.append("candidate should answer current interview question")
    elif match.get("status") == "manager_review":
        next_checks.append("manager can approve or reject candidate")

    if next_checks:
        _print("next_checks", " | ".join(next_checks))


if __name__ == "__main__":
    main()
