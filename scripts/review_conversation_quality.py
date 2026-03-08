#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from scripts.export_telegram_conversation import ConversationTurn, load_conversation


ROBOTIC_PATTERNS: list[tuple[str, str, str]] = [
    ("processing_started", "processing started", "runtime microcopy"),
    ("processing_now", "processing it now", "runtime microcopy"),
    ("please_answer_with", "please answer with", "runtime microcopy"),
    ("please_send", "please send", "runtime microcopy"),
    ("understood_i_will", "understood. i will", "stage prompt or runtime microcopy"),
    ("thanks_i_will", "thanks. i will", "stage prompt or runtime microcopy"),
    ("final_version", "final version for approval", "summary review messaging"),
    ("not_expected", "not expected at the current step", "fallback/recovery copy"),
    ("unsupported", "unsupported", "fallback/recovery copy"),
    ("inconsistent", "inconsistent", "interview runtime error copy"),
]


@dataclass
class RoboticFinding:
    created_at: str
    speaker: str
    text: str
    pattern_key: str
    likely_fix_area: str


def find_robotic_turns(turns: list[ConversationTurn], *, limit: int) -> list[RoboticFinding]:
    findings: list[RoboticFinding] = []
    for turn in turns:
        if turn.speaker != "Helly":
            continue
        text = (turn.text or "").strip()
        lowered = text.lower()
        for pattern_key, fragment, likely_fix_area in ROBOTIC_PATTERNS:
            if fragment in lowered:
                findings.append(
                    RoboticFinding(
                        created_at=turn.created_at,
                        speaker=turn.speaker,
                        text=text,
                        pattern_key=pattern_key,
                        likely_fix_area=likely_fix_area,
                    )
                )
                break
        if len(findings) >= limit:
            break
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review recent Telegram conversation turns and flag likely robotic Helly replies."
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--include-pending-notifications", action="store_true")
    args = parser.parse_args()

    turns = load_conversation(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
        limit=args.limit,
        include_pending_notifications=args.include_pending_notifications,
    )
    findings = find_robotic_turns(turns, limit=args.top)

    if args.format == "json":
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
        return

    if not turns:
        print("status: not_found")
        return

    print("status: found")
    print(f"conversation_turns: {len(turns)}")
    print(f"robotic_findings: {len(findings)}")
    for idx, finding in enumerate(findings, start=1):
        print(f"{idx}. [{finding.pattern_key}] {finding.created_at}")
        print(f"   text: {finding.text}")
        print(f"   likely_fix_area: {finding.likely_fix_area}")


if __name__ == "__main__":
    main()
