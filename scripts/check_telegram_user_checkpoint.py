#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

from scripts.inspect_telegram_user import load_snapshot


def _matches(snapshot, args) -> tuple[bool, list[str]]:
    checks: list[str] = []
    matched = True

    if args.require_user:
        actual = snapshot.user is not None
        checks.append(f"user={'present' if actual else 'missing'}")
        matched = matched and actual

    if args.expect_candidate_state is not None:
        actual = (snapshot.candidate_profile or {}).get("state")
        checks.append(f"candidate_state={actual}")
        matched = matched and actual == args.expect_candidate_state

    if args.expect_vacancy_state is not None:
        actual = (snapshot.vacancy or {}).get("state")
        checks.append(f"vacancy_state={actual}")
        matched = matched and actual == args.expect_vacancy_state

    if args.expect_interview_state is not None:
        actual = (snapshot.interview_session or {}).get("state")
        checks.append(f"interview_state={actual}")
        matched = matched and actual == args.expect_interview_state

    if args.expect_match_status is not None:
        actual = (snapshot.invited_match or {}).get("status")
        checks.append(f"match_status={actual}")
        matched = matched and actual == args.expect_match_status

    if args.expect_notification_template is not None:
        actual = (snapshot.latest_notification or {}).get("template_key")
        checks.append(f"latest_notification={actual}")
        matched = matched and actual == args.expect_notification_template

    return matched, checks


def _print_report(snapshot) -> None:
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
    print(f"user_id: {user['id']}")
    print(f"telegram_user_id: {user['telegram_user_id']}")
    print(f"telegram_chat_id: {user['telegram_chat_id']}")
    print(f"candidate_state: {candidate.get('state')}")
    print(f"vacancy_state: {vacancy.get('state')}")
    print(f"match_status: {match.get('status')}")
    print(f"interview_state: {interview.get('state')}")
    print(f"latest_notification: {notification.get('template_key')}")
    if snapshot.counts:
        counts = ", ".join(
            f"{key}={value}" for key, value in sorted(snapshot.counts.items())
        )
        print(f"counts: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wait for a live Telegram smoke checkpoint, then print a compact status report"
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument("--expect-candidate-state", default=None)
    parser.add_argument("--expect-vacancy-state", default=None)
    parser.add_argument("--expect-interview-state", default=None)
    parser.add_argument("--expect-match-status", default=None)
    parser.add_argument("--expect-notification-template", default=None)
    parser.add_argument("--require-user", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()

    started_at = time.monotonic()
    attempt = 0
    final_snapshot = None

    while True:
        attempt += 1
        snapshot = load_snapshot(
            telegram_user_id=args.telegram_user_id,
            telegram_chat_id=args.telegram_chat_id,
        )
        matched, checks = _matches(snapshot, args)
        elapsed = time.monotonic() - started_at
        print(
            f"attempt={attempt} elapsed={elapsed:.1f}s "
            + ("matched " if matched else "waiting ")
            + " ".join(checks or ["no_expectations"])
        )
        final_snapshot = snapshot
        if matched:
            break
        if elapsed >= args.timeout_seconds:
            _print_report(snapshot)
            print("checkpoint: timeout", file=sys.stderr)
            raise SystemExit(1)
        time.sleep(args.interval_seconds)

    _print_report(final_snapshot)
    print("checkpoint: ok")


if __name__ == "__main__":
    main()
