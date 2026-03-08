#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

from src.db.session import get_engine


@dataclass
class Snapshot:
    user: dict[str, Any] | None
    candidate_profile: dict[str, Any] | None
    candidate_version: dict[str, Any] | None
    vacancy: dict[str, Any] | None
    vacancy_version: dict[str, Any] | None
    invited_match: dict[str, Any] | None
    interview_session: dict[str, Any] | None
    evaluation_result: dict[str, Any] | None
    latest_notification: dict[str, Any] | None
    counts: dict[str, int]


def _one(conn, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def _count(conn, sql: str, params: dict[str, Any]) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


def load_snapshot(*, telegram_user_id: int | None, telegram_chat_id: int | None) -> Snapshot:
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
        user = _one(
            conn,
            f"""
            select id, telegram_user_id, telegram_chat_id, phone_number, display_name, username,
                   language_code, timezone, is_candidate, is_hiring_manager, deleted_at, created_at, updated_at
            from users
            where {user_filter}
            order by created_at desc
            limit 1
            """,
            params,
        )

        if user is None:
            return Snapshot(
                user=None,
                candidate_profile=None,
                candidate_version=None,
                vacancy=None,
                vacancy_version=None,
                invited_match=None,
                interview_session=None,
                evaluation_result=None,
                latest_notification=None,
                counts={},
            )

        entity_params = {"user_id": user["id"]}

        candidate_profile = _one(
            conn,
            """
            select id, state, current_version_id, salary_min, salary_max, salary_currency, salary_period,
                   location_text, country_code, city, work_format, seniority_normalized, target_role,
                   ready_at, deleted_at, created_at, updated_at
            from candidate_profiles
            where user_id = :user_id
            order by created_at desc
            limit 1
            """,
            entity_params,
        )

        candidate_version = None
        invited_match = None
        interview_session = None
        evaluation_result = None
        if candidate_profile is not None:
            candidate_version = _one(
                conn,
                """
                select id, profile_id, version_no, source_type, approval_status, approved_by_user,
                       prompt_version, model_name, extracted_text, transcript_text, summary_json, created_at
                from candidate_profile_versions
                where profile_id = :profile_id
                order by version_no desc
                limit 1
                """,
                {"profile_id": candidate_profile["id"]},
            )
            invited_match = _one(
                conn,
                """
                select id, matching_run_id, vacancy_id, status, hard_filter_passed, embedding_score,
                       deterministic_score, llm_rank_score, llm_rank_position, invitation_sent_at,
                       candidate_response_at, manager_decision_at, updated_at
                from matches
                where candidate_profile_id = :profile_id
                order by updated_at desc
                limit 1
                """,
                {"profile_id": candidate_profile["id"]},
            )
            interview_session = _one(
                conn,
                """
                select id, match_id, vacancy_id, state, current_question_order, total_questions,
                       invited_at, accepted_at, started_at, completed_at, expires_at, updated_at
                from interview_sessions
                where candidate_profile_id = :profile_id
                order by updated_at desc
                limit 1
                """,
                {"profile_id": candidate_profile["id"]},
            )
            if interview_session is not None:
                evaluation_result = _one(
                    conn,
                    """
                    select id, match_id, interview_session_id, status, final_score, recommendation,
                           strengths_json, risks_json, created_at
                    from evaluation_results
                    where interview_session_id = :session_id
                    order by created_at desc
                    limit 1
                    """,
                    {"session_id": interview_session["id"]},
                )

        vacancy = _one(
            conn,
            """
            select id, state, current_version_id, role_title, seniority_normalized, budget_min, budget_max,
                   budget_currency, budget_period, work_format, team_size, opened_at, deleted_at, created_at, updated_at
            from vacancies
            where manager_user_id = :user_id
            order by created_at desc
            limit 1
            """,
            entity_params,
        )
        vacancy_version = None
        if vacancy is not None:
            vacancy_version = _one(
                conn,
                """
                select id, vacancy_id, version_no, source_type, prompt_version, model_name,
                       extracted_text, transcript_text, summary_json, inconsistency_json, created_at
                from vacancy_versions
                where vacancy_id = :vacancy_id
                order by version_no desc
                limit 1
                """,
                {"vacancy_id": vacancy["id"]},
            )

        latest_notification = _one(
            conn,
            """
            select id, template_key, status, entity_type, entity_id, payload_json, created_at, updated_at
            from notifications
            where user_id = :user_id
            order by created_at desc
            limit 1
            """,
            entity_params,
        )

        counts = {
            "raw_messages": _count(
                conn,
                "select count(*) from raw_messages where user_id = :user_id",
                entity_params,
            ),
            "notifications": _count(
                conn,
                "select count(*) from notifications where user_id = :user_id",
                entity_params,
            ),
            "files": _count(
                conn,
                "select count(*) from files where owner_user_id = :user_id",
                entity_params,
            ),
            "matches": _count(
                conn,
                """
                select count(*)
                from matches m
                join candidate_profiles cp on cp.id = m.candidate_profile_id
                where cp.user_id = :user_id
                """,
                entity_params,
            ),
            "vacancies": _count(
                conn,
                "select count(*) from vacancies where manager_user_id = :user_id",
                entity_params,
            ),
        }

    return Snapshot(
        user=user,
        candidate_profile=candidate_profile,
        candidate_version=candidate_version,
        vacancy=vacancy,
        vacancy_version=vacancy_version,
        invited_match=invited_match,
        interview_session=interview_session,
        evaluation_result=evaluation_result,
        latest_notification=latest_notification,
        counts=counts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Helly production state for a Telegram user")
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    args = parser.parse_args()

    snapshot = load_snapshot(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
    )
    print(json.dumps(asdict(snapshot), indent=2, default=str))


if __name__ == "__main__":
    main()
