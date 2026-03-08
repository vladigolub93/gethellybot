#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

from src.db.session import get_engine


@dataclass
class ConversationTurn:
    created_at: str
    direction: str
    content_type: str
    speaker: str
    text: str | None


def _load_user_id(*, telegram_user_id: int | None, telegram_chat_id: int | None) -> str | None:
    if telegram_user_id is None and telegram_chat_id is None:
        raise ValueError("Either telegram_user_id or telegram_chat_id is required")

    params = {
        "telegram_user_id": telegram_user_id,
        "telegram_chat_id": telegram_chat_id,
    }
    user_filter = (
        "telegram_user_id = :telegram_user_id"
        if telegram_user_id is not None
        else "telegram_chat_id = :telegram_chat_id"
    )
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                f"""
                select id
                from users
                where {user_filter}
                order by created_at desc
                limit 1
                """
            ),
            params,
        ).mappings().first()
        return str(row["id"]) if row else None


def load_conversation(
    *,
    telegram_user_id: int | None,
    telegram_chat_id: int | None,
    limit: int,
) -> list[ConversationTurn]:
    user_id = _load_user_id(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
    )
    if user_id is None:
        return []

    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                select created_at, direction, content_type, text_content
                from raw_messages
                where user_id = cast(:user_id as uuid)
                order by created_at desc
                limit :limit
                """
            ),
            {"user_id": user_id, "limit": limit},
        ).mappings().all()

    turns: list[ConversationTurn] = []
    for row in reversed(rows):
        direction = row["direction"]
        turns.append(
            ConversationTurn(
                created_at=str(row["created_at"]),
                direction=direction,
                content_type=row["content_type"],
                speaker="User" if direction == "inbound" else "Helly",
                text=row["text_content"],
            )
        )
    return turns


def _print_markdown(turns: list[ConversationTurn]) -> None:
    if not turns:
        print("status: not_found")
        return
    print("# Telegram Conversation")
    for turn in turns:
        text = (turn.text or "").strip() or f"[{turn.content_type}]"
        print(f"- {turn.created_at} {turn.speaker}: {text}")


def _print_text(turns: list[ConversationTurn]) -> None:
    if not turns:
        print("status: not_found")
        return
    for turn in turns:
        text = (turn.text or "").strip() or f"[{turn.content_type}]"
        print(f"{turn.created_at} {turn.speaker}: {text}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export recent Telegram conversation turns for one Helly user."
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    args = parser.parse_args()

    turns = load_conversation(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
        limit=args.limit,
    )

    if args.format == "json":
        print(json.dumps([asdict(turn) for turn in turns], ensure_ascii=False, indent=2))
        return
    if args.format == "markdown":
        _print_markdown(turns)
        return
    _print_text(turns)


if __name__ == "__main__":
    main()
