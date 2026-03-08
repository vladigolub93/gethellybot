#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sqlalchemy import text

from scripts.inspect_telegram_user import load_snapshot
from scripts.validate_graph_stage_logs import _fetch_logs, _matches
from src.db.session import get_engine


def _fail(message: str, **payload: Any) -> None:
    print(json.dumps({"status": "failed", "message": message, **payload}, default=str, indent=2))
    raise SystemExit(1)


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
        description="Validate a live Helly stage checkpoint across DB state, help-safety, transition-safety, and Railway logs."
    )
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--expect-candidate-state")
    parser.add_argument("--expect-vacancy-state")
    parser.add_argument("--expect-interview-state")
    parser.add_argument("--expect-match-status")
    parser.add_argument("--expect-notification-template")
    parser.add_argument("--expect-inbound-contains")
    parser.add_argument("--forbid-candidate-version-source-type")
    parser.add_argument("--forbid-vacancy-version-source-type")
    parser.add_argument("--expect-log-stage")
    parser.add_argument("--allow-transition", action="store_true")
    parser.add_argument("--railway-token")
    parser.add_argument("--railway-environment-id")
    args = parser.parse_args()

    snapshot = load_snapshot(telegram_user_id=args.telegram_user_id, telegram_chat_id=None)
    if snapshot.user is None:
        _fail("user_not_found", telegram_user_id=args.telegram_user_id)

    user = snapshot.user
    candidate = snapshot.candidate_profile or {}
    vacancy = snapshot.vacancy or {}
    interview = snapshot.interview_session or {}
    match = snapshot.invited_match or {}
    notification = snapshot.latest_notification or {}
    candidate_version = snapshot.candidate_version or {}
    vacancy_version = snapshot.vacancy_version or {}

    latest_inbound, latest_transition = _latest_inbound_and_transition(user_id=user["id"])

    payload = {
        "telegram_user_id": args.telegram_user_id,
        "candidate_state": candidate.get("state"),
        "vacancy_state": vacancy.get("state"),
        "interview_state": interview.get("state"),
        "match_status": match.get("status"),
        "latest_notification": notification.get("template_key"),
        "candidate_version_source_type": candidate_version.get("source_type"),
        "vacancy_version_source_type": vacancy_version.get("source_type"),
        "latest_inbound": latest_inbound,
        "latest_transition": latest_transition,
    }

    if args.expect_candidate_state and candidate.get("state") != args.expect_candidate_state:
        _fail("unexpected_candidate_state", **payload)
    if args.expect_vacancy_state and vacancy.get("state") != args.expect_vacancy_state:
        _fail("unexpected_vacancy_state", **payload)
    if args.expect_interview_state and interview.get("state") != args.expect_interview_state:
        _fail("unexpected_interview_state", **payload)
    if args.expect_match_status and match.get("status") != args.expect_match_status:
        _fail("unexpected_match_status", **payload)
    if args.expect_notification_template and notification.get("template_key") != args.expect_notification_template:
        _fail("unexpected_notification_template", **payload)

    if args.expect_inbound_contains:
        inbound_text = (latest_inbound or {}).get("text_content") or ""
        if args.expect_inbound_contains not in inbound_text:
            _fail("latest_inbound_text_mismatch", **payload)

    if (
        args.forbid_candidate_version_source_type
        and candidate_version.get("source_type") == args.forbid_candidate_version_source_type
    ):
        _fail("forbidden_candidate_version_source_type", **payload)
    if (
        args.forbid_vacancy_version_source_type
        and vacancy_version.get("source_type") == args.forbid_vacancy_version_source_type
    ):
        _fail("forbidden_vacancy_version_source_type", **payload)

    if not args.allow_transition and latest_inbound is not None and latest_transition is not None:
        if latest_transition["created_at"] >= latest_inbound["created_at"]:
            _fail("unexpected_transition_after_latest_inbound", **payload)

    log_result = None
    if args.expect_log_stage:
        token = args.railway_token
        environment_id = args.railway_environment_id
        if not token or not environment_id:
            _fail(
                "missing_railway_log_credentials",
                missing=[
                    name
                    for name, value in {
                        "railway_token": token,
                        "railway_environment_id": environment_id,
                    }.items()
                    if not value
                ],
                **payload,
            )

        logs = _fetch_logs(token=token, environment_id=environment_id, limit=100, pages=2)
        matches = [
            log
            for log in logs
            if _matches(
                log,
                contains="graph_stage_executed",
                expected_stage=args.expect_log_stage,
                expected_telegram_user_id=str(args.telegram_user_id),
            )
        ]
        if not matches:
            _fail("missing_graph_stage_log", scanned_logs=len(logs), expected_stage=args.expect_log_stage, **payload)
        log_result = matches[0]

    print(
        json.dumps(
            {
                "status": "ok",
                **payload,
                "log_match": log_result,
            },
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
