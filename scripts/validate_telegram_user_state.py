#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from scripts.inspect_telegram_user import load_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Helly live state for a Telegram user after a manual smoke test"
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument("--expect-candidate-state", default=None)
    parser.add_argument("--expect-vacancy-state", default=None)
    parser.add_argument("--expect-interview-state", default=None)
    parser.add_argument("--expect-match-status", default=None)
    parser.add_argument("--expect-notification-template", default=None)
    parser.add_argument("--require-user", action="store_true")
    args = parser.parse_args()

    snapshot = load_snapshot(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
    )

    failures: list[str] = []

    if args.require_user and snapshot.user is None:
        failures.append("Expected user record, but none was found.")

    if args.expect_candidate_state is not None:
        actual = (snapshot.candidate_profile or {}).get("state")
        if actual != args.expect_candidate_state:
            failures.append(
                f"Candidate state mismatch: expected {args.expect_candidate_state}, got {actual}"
            )

    if args.expect_vacancy_state is not None:
        actual = (snapshot.vacancy or {}).get("state")
        if actual != args.expect_vacancy_state:
            failures.append(
                f"Vacancy state mismatch: expected {args.expect_vacancy_state}, got {actual}"
            )

    if args.expect_interview_state is not None:
        actual = (snapshot.interview_session or {}).get("state")
        if actual != args.expect_interview_state:
            failures.append(
                f"Interview state mismatch: expected {args.expect_interview_state}, got {actual}"
            )

    if args.expect_match_status is not None:
        actual = (snapshot.invited_match or {}).get("status")
        if actual != args.expect_match_status:
            failures.append(
                f"Match status mismatch: expected {args.expect_match_status}, got {actual}"
            )

    if args.expect_notification_template is not None:
        actual = (snapshot.latest_notification or {}).get("template_key")
        if actual != args.expect_notification_template:
            failures.append(
                f"Latest notification mismatch: expected {args.expect_notification_template}, got {actual}"
            )

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)

    print("validation: ok")
    if snapshot.user is not None:
        print(f"user_id: {snapshot.user['id']}")
    if snapshot.candidate_profile is not None:
        print(f"candidate_state: {snapshot.candidate_profile.get('state')}")
    if snapshot.vacancy is not None:
        print(f"vacancy_state: {snapshot.vacancy.get('state')}")
    if snapshot.interview_session is not None:
        print(f"interview_state: {snapshot.interview_session.get('state')}")
    if snapshot.invited_match is not None:
        print(f"match_status: {snapshot.invited_match.get('status')}")
    if snapshot.latest_notification is not None:
        print(f"latest_notification: {snapshot.latest_notification.get('template_key')}")


if __name__ == "__main__":
    main()
