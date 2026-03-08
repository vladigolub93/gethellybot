#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import bindparam, text

from scripts.inspect_telegram_user import load_snapshot
from src.db.session import get_engine


def _select_ids(conn, sql: str, params: dict[str, Any]) -> list[str]:
    return [str(row[0]) for row in conn.execute(text(sql), params).all()]


def _delete_by_ids(conn, sql: str, ids: Sequence[str]) -> int:
    if not ids:
        return 0
    stmt = text(sql).bindparams(bindparam("ids", expanding=True))
    return int(conn.execute(stmt, {"ids": list(ids)}).rowcount or 0)


def _delete_scalar(conn, sql: str, params: dict[str, Any]) -> int:
    return int(conn.execute(text(sql), params).rowcount or 0)


def build_plan(*, user_id: str) -> dict[str, list[str]]:
    with get_engine().connect() as conn:
        candidate_profile_ids = _select_ids(
            conn,
            "select id from candidate_profiles where user_id = :user_id",
            {"user_id": user_id},
        )
        vacancy_ids = _select_ids(
            conn,
            "select id from vacancies where manager_user_id = :user_id",
            {"user_id": user_id},
        )
        candidate_version_ids = (
            _select_ids(
                conn,
                "select id from candidate_profile_versions where profile_id = any(:profile_ids)",
                {"profile_ids": candidate_profile_ids},
            )
            if candidate_profile_ids
            else []
        )
        vacancy_version_ids = (
            _select_ids(
                conn,
                "select id from vacancy_versions where vacancy_id = any(:vacancy_ids)",
                {"vacancy_ids": vacancy_ids},
            )
            if vacancy_ids
            else []
        )
        matching_run_ids = _select_ids(
            conn,
            """
            select id
            from matching_runs
            where vacancy_id = any(:vacancy_ids)
               or trigger_candidate_profile_id = any(:candidate_profile_ids)
            """,
            {
                "vacancy_ids": vacancy_ids or [None],
                "candidate_profile_ids": candidate_profile_ids or [None],
            },
        )
        match_ids = _select_ids(
            conn,
            """
            select id
            from matches
            where candidate_profile_id = any(:candidate_profile_ids)
               or vacancy_id = any(:vacancy_ids)
               or matching_run_id = any(:matching_run_ids)
            """,
            {
                "candidate_profile_ids": candidate_profile_ids or [None],
                "vacancy_ids": vacancy_ids or [None],
                "matching_run_ids": matching_run_ids or [None],
            },
        )
        invite_wave_ids = (
            _select_ids(
                conn,
                """
                select id
                from invite_waves
                where vacancy_id = any(:vacancy_ids)
                   or matching_run_id = any(:matching_run_ids)
                """,
                {
                    "vacancy_ids": vacancy_ids or [None],
                    "matching_run_ids": matching_run_ids or [None],
                },
            )
            if vacancy_ids or matching_run_ids
            else []
        )
        interview_session_ids = _select_ids(
            conn,
            """
            select id
            from interview_sessions
            where candidate_profile_id = any(:candidate_profile_ids)
               or vacancy_id = any(:vacancy_ids)
               or match_id = any(:match_ids)
            """,
            {
                "candidate_profile_ids": candidate_profile_ids or [None],
                "vacancy_ids": vacancy_ids or [None],
                "match_ids": match_ids or [None],
            },
        )
        interview_question_ids = (
            _select_ids(
                conn,
                "select id from interview_questions where session_id = any(:session_ids)",
                {"session_ids": interview_session_ids},
            )
            if interview_session_ids
            else []
        )

    return {
        "candidate_profile_ids": candidate_profile_ids,
        "candidate_version_ids": candidate_version_ids,
        "vacancy_ids": vacancy_ids,
        "vacancy_version_ids": vacancy_version_ids,
        "matching_run_ids": matching_run_ids,
        "match_ids": match_ids,
        "invite_wave_ids": invite_wave_ids,
        "interview_session_ids": interview_session_ids,
        "interview_question_ids": interview_question_ids,
    }


def reset_user(*, user_id: str, plan: dict[str, list[str]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    with get_engine().begin() as conn:
        summary["introduction_events"] = _delete_scalar(
            conn,
            """
            delete from introduction_events
            where candidate_user_id = :user_id
               or manager_user_id = :user_id
               or match_id = any(:match_ids)
            """,
            {"user_id": user_id, "match_ids": plan["match_ids"] or [None]},
        )
        summary["evaluation_results"] = _delete_scalar(
            conn,
            """
            delete from evaluation_results
            where match_id = any(:match_ids)
               or interview_session_id = any(:session_ids)
            """,
            {
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["interview_answers"] = _delete_scalar(
            conn,
            """
            delete from interview_answers
            where session_id = any(:session_ids)
               or question_id = any(:question_ids)
            """,
            {
                "session_ids": plan["interview_session_ids"] or [None],
                "question_ids": plan["interview_question_ids"] or [None],
            },
        )
        summary["interview_questions"] = _delete_by_ids(
            conn,
            "delete from interview_questions where id in :ids",
            plan["interview_question_ids"],
        )
        summary["interview_sessions"] = _delete_by_ids(
            conn,
            "delete from interview_sessions where id in :ids",
            plan["interview_session_ids"],
        )
        summary["invite_waves"] = _delete_by_ids(
            conn,
            "delete from invite_waves where id in :ids",
            plan["invite_wave_ids"],
        )
        summary["matches"] = _delete_by_ids(
            conn,
            "delete from matches where id in :ids",
            plan["match_ids"],
        )
        summary["matching_runs"] = _delete_by_ids(
            conn,
            "delete from matching_runs where id in :ids",
            plan["matching_run_ids"],
        )
        summary["candidate_verifications"] = _delete_scalar(
            conn,
            "delete from candidate_verifications where profile_id = any(:profile_ids)",
            {"profile_ids": plan["candidate_profile_ids"] or [None]},
        )
        summary["candidate_profile_current_version_unlinks"] = _delete_scalar(
            conn,
            """
            update candidate_profiles
            set current_version_id = null
            where user_id = :user_id
              and current_version_id is not null
            """,
            {"user_id": user_id},
        )
        summary["vacancy_current_version_unlinks"] = _delete_scalar(
            conn,
            """
            update vacancies
            set current_version_id = null
            where manager_user_id = :user_id
              and current_version_id is not null
            """,
            {"user_id": user_id},
        )
        summary["candidate_profile_versions"] = _delete_by_ids(
            conn,
            "delete from candidate_profile_versions where id in :ids",
            plan["candidate_version_ids"],
        )
        summary["vacancy_versions"] = _delete_by_ids(
            conn,
            "delete from vacancy_versions where id in :ids",
            plan["vacancy_version_ids"],
        )
        summary["notifications"] = _delete_scalar(
            conn,
            "delete from notifications where user_id = :user_id",
            {"user_id": user_id},
        )
        summary["outbox_events"] = _delete_scalar(
            conn,
            """
            delete from outbox_events
            where (entity_type = 'user' and entity_id = cast(:user_id as uuid))
               or (entity_type = 'candidate_profile' and entity_id = any(:candidate_profile_ids))
               or (entity_type = 'vacancy' and entity_id = any(:vacancy_ids))
               or (entity_type = 'match' and entity_id = any(:match_ids))
               or (entity_type = 'interview_session' and entity_id = any(:session_ids))
            """,
            {
                "user_id": user_id,
                "candidate_profile_ids": plan["candidate_profile_ids"] or [None],
                "vacancy_ids": plan["vacancy_ids"] or [None],
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["state_transition_logs"] = _delete_scalar(
            conn,
            """
            delete from state_transition_logs
            where actor_user_id = :user_id
               or (entity_type = 'candidate_profile' and entity_id = any(:candidate_profile_ids))
               or (entity_type = 'vacancy' and entity_id = any(:vacancy_ids))
               or (entity_type = 'match' and entity_id = any(:match_ids))
               or (entity_type = 'interview_session' and entity_id = any(:session_ids))
            """,
            {
                "user_id": user_id,
                "candidate_profile_ids": plan["candidate_profile_ids"] or [None],
                "vacancy_ids": plan["vacancy_ids"] or [None],
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["job_execution_logs"] = _delete_scalar(
            conn,
            """
            delete from job_execution_logs
            where (entity_type = 'candidate_profile' and entity_id = any(:candidate_profile_ids))
               or (entity_type = 'vacancy' and entity_id = any(:vacancy_ids))
               or (entity_type = 'match' and entity_id = any(:match_ids))
               or (entity_type = 'interview_session' and entity_id = any(:session_ids))
            """,
            {
                "candidate_profile_ids": plan["candidate_profile_ids"] or [None],
                "vacancy_ids": plan["vacancy_ids"] or [None],
                "match_ids": plan["match_ids"] or [None],
                "session_ids": plan["interview_session_ids"] or [None],
            },
        )
        summary["user_consents"] = _delete_scalar(
            conn,
            "delete from user_consents where user_id = :user_id",
            {"user_id": user_id},
        )
        summary["raw_messages"] = _delete_scalar(
            conn,
            "delete from raw_messages where user_id = :user_id",
            {"user_id": user_id},
        )
        summary["files"] = _delete_scalar(
            conn,
            "delete from files where owner_user_id = :user_id",
            {"user_id": user_id},
        )
        summary["candidate_profiles"] = _delete_scalar(
            conn,
            "delete from candidate_profiles where user_id = :user_id",
            {"user_id": user_id},
        )
        summary["vacancies"] = _delete_scalar(
            conn,
            "delete from vacancies where manager_user_id = :user_id",
            {"user_id": user_id},
        )
        summary["users"] = _delete_scalar(
            conn,
            "delete from users where id = :user_id",
            {"user_id": user_id},
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset all Helly data for a Telegram user to enable a clean live smoke run"
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the reset. Without this flag the script prints the deletion plan only.",
    )
    args = parser.parse_args()

    snapshot = load_snapshot(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
    )
    if snapshot.user is None:
        print(json.dumps({"status": "not_found"}, indent=2))
        return

    user_id = snapshot.user["id"]
    plan = build_plan(user_id=user_id)
    payload: dict[str, Any] = {
        "status": "planned",
        "user_id": user_id,
        "telegram_user_id": snapshot.user["telegram_user_id"],
        "telegram_chat_id": snapshot.user["telegram_chat_id"],
        "plan": {key: len(value) for key, value in plan.items()},
    }

    if args.execute:
        payload["status"] = "executed"
        payload["deleted"] = reset_user(user_id=user_id, plan=plan)

    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
