#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sqlalchemy import text

from scripts.inspect_telegram_user import load_snapshot
from src.db.session import get_engine


def _latest_inbound_message(*, user_id: str) -> dict[str, Any] | None:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                """
                select id, content_type, text_content, created_at
                from raw_messages
                where user_id = :user_id and direction = 'inbound'
                order by created_at desc
                limit 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        return dict(row) if row else None


def _fail(message: str, payload: dict[str, Any]) -> None:
    print(json.dumps({"status": "failed", "message": message, **payload}, default=str, indent=2))
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate that a help/clarification message did not trigger an incorrect stage transition"
    )
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--expect-candidate-state")
    parser.add_argument("--expect-vacancy-state")
    parser.add_argument("--expect-latest-inbound-contains")
    parser.add_argument("--expect-latest-notification")
    parser.add_argument("--forbid-latest-notification")
    parser.add_argument("--forbid-candidate-version-source-type")
    parser.add_argument("--forbid-vacancy-version-source-type")
    args = parser.parse_args()

    snapshot = load_snapshot(telegram_user_id=args.telegram_user_id, telegram_chat_id=None)
    if snapshot.user is None:
        _fail("user_not_found", {"telegram_user_id": args.telegram_user_id})

    user_id = snapshot.user["id"]
    latest_inbound = _latest_inbound_message(user_id=user_id)
    latest_notification = snapshot.latest_notification or {}
    candidate = snapshot.candidate_profile or {}
    vacancy = snapshot.vacancy or {}
    candidate_version = snapshot.candidate_version or {}
    vacancy_version = snapshot.vacancy_version or {}

    payload = {
        "telegram_user_id": args.telegram_user_id,
        "candidate_state": candidate.get("state"),
        "vacancy_state": vacancy.get("state"),
        "latest_inbound": latest_inbound,
        "latest_notification": latest_notification.get("template_key"),
        "candidate_version_source_type": candidate_version.get("source_type"),
        "vacancy_version_source_type": vacancy_version.get("source_type"),
    }

    if args.expect_candidate_state and candidate.get("state") != args.expect_candidate_state:
        _fail("unexpected_candidate_state", payload)
    if args.expect_vacancy_state and vacancy.get("state") != args.expect_vacancy_state:
        _fail("unexpected_vacancy_state", payload)
    if args.expect_latest_inbound_contains:
        inbound_text = (latest_inbound or {}).get("text_content") or ""
        if args.expect_latest_inbound_contains not in inbound_text:
            _fail("latest_inbound_text_mismatch", payload)
    if args.expect_latest_notification and latest_notification.get("template_key") != args.expect_latest_notification:
        _fail("unexpected_latest_notification", payload)
    if args.forbid_latest_notification and latest_notification.get("template_key") == args.forbid_latest_notification:
        _fail("forbidden_latest_notification", payload)
    if (
        args.forbid_candidate_version_source_type
        and candidate_version.get("source_type") == args.forbid_candidate_version_source_type
    ):
        _fail("forbidden_candidate_version_source_type", payload)
    if (
        args.forbid_vacancy_version_source_type
        and vacancy_version.get("source_type") == args.forbid_vacancy_version_source_type
    ):
        _fail("forbidden_vacancy_version_source_type", payload)

    print(json.dumps({"status": "ok", **payload}, default=str, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
