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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch Helly live state for one Telegram user until expected conditions are reached"
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
        if matched:
            print("watch: matched")
            return
        if elapsed >= args.timeout_seconds:
            print("watch: timeout", file=sys.stderr)
            raise SystemExit(1)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
