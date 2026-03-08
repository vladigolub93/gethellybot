#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sqlalchemy import text

from scripts.inspect_telegram_user import load_snapshot
from src.db.session import get_engine


def _latest_inbound_and_transition(*, user_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    with get_engine().connect() as conn:
        latest_inbound = conn.execute(
            text(
                """
                select id, text_content, content_type, created_at
                from raw_messages
                where user_id = :user_id and direction = 'inbound'
                order by created_at desc
                limit 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        latest_transition = conn.execute(
            text(
                """
                select id, entity_type, from_state, to_state, created_at
                from state_transition_logs
                where actor_user_id = :user_id
                order by created_at desc
                limit 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        return (
            dict(latest_inbound) if latest_inbound else None,
            dict(latest_transition) if latest_transition else None,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate that no unexpected state transition happened after the latest inbound Telegram message"
    )
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--allow-transition", action="store_true")
    parser.add_argument("--expect-inbound-contains")
    args = parser.parse_args()

    snapshot = load_snapshot(telegram_user_id=args.telegram_user_id, telegram_chat_id=None)
    if snapshot.user is None:
        print(json.dumps({"status": "failed", "message": "user_not_found"}, indent=2))
        raise SystemExit(1)

    latest_inbound, latest_transition = _latest_inbound_and_transition(user_id=snapshot.user["id"])
    payload = {
        "status": "ok",
        "telegram_user_id": args.telegram_user_id,
        "latest_inbound": latest_inbound,
        "latest_transition": latest_transition,
    }

    if latest_inbound is None:
        payload["status"] = "failed"
        payload["message"] = "no_inbound_message_found"
        print(json.dumps(payload, default=str, indent=2))
        raise SystemExit(1)

    if args.expect_inbound_contains and args.expect_inbound_contains not in ((latest_inbound or {}).get("text_content") or ""):
        payload["status"] = "failed"
        payload["message"] = "latest_inbound_text_mismatch"
        print(json.dumps(payload, default=str, indent=2))
        raise SystemExit(1)

    if not args.allow_transition and latest_transition is not None:
        inbound_at = latest_inbound["created_at"]
        transition_at = latest_transition["created_at"]
        if transition_at >= inbound_at:
            payload["status"] = "failed"
            payload["message"] = "unexpected_transition_after_latest_inbound"
            print(json.dumps(payload, default=str, indent=2))
            raise SystemExit(1)

    print(json.dumps(payload, default=str, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
