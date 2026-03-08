#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from apps.worker.main import _process_job
from scripts.inspect_telegram_user import load_snapshot
from src.config.logging import configure_logging
from src.config.settings import get_settings
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.session import get_session_factory
from src.telegram.normalizer import normalize_telegram_update
from src.telegram.service import TelegramUpdateService


def _build_message_payload(
    *,
    update_id: int,
    telegram_user_id: int,
    telegram_chat_id: int,
    message_id: int,
    display_name: str,
    username: str | None,
    language_code: str,
    content_type: str,
    text: str | None,
    contact_phone_number: str | None,
) -> dict[str, Any]:
    first_name, _, last_name = display_name.partition(" ")
    message: dict[str, Any] = {
        "message_id": message_id,
        "date": int(time.time()),
        "chat": {
            "id": telegram_chat_id,
            "type": "private",
            "first_name": first_name or display_name,
            "last_name": last_name or None,
            "username": username,
        },
        "from": {
            "id": telegram_user_id,
            "is_bot": False,
            "first_name": first_name or display_name,
            "last_name": last_name or None,
            "username": username,
            "language_code": language_code,
        },
    }

    if content_type == "contact":
        message["contact"] = {
            "phone_number": contact_phone_number,
            "first_name": first_name or display_name,
            "last_name": last_name or None,
            "user_id": telegram_user_id,
        }
    else:
        message["text"] = text

    return {"update_id": update_id, "message": message}


def _drain_worker_queue(*, max_jobs: int, deliver_notifications: bool) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    processed: list[dict[str, Any]] = []

    for _ in range(max_jobs):
        session = session_factory()
        try:
            repo = JobExecutionLogsRepository(session)
            job = repo.claim_next_queued()
            if job is None:
                session.commit()
                break
            if job.job_type.startswith("notification_") and not deliver_notifications:
                session.commit()
                break

            repo.mark_started(job)
            result = _process_job(session, job)
            repo.mark_completed(job, result_json=result)
            session.commit()
            processed.append(
                {
                    "job_type": job.job_type,
                    "entity_type": job.entity_type,
                    "entity_id": str(job.entity_id) if job.entity_id is not None else None,
                    "result": result,
                }
            )
        except Exception as exc:
            session.rollback()
            if "job" in locals() and job is not None:
                failure_session = session_factory()
                try:
                    failure_repo = JobExecutionLogsRepository(failure_session)
                    failed_job = failure_repo.get_by_id(job.id)
                    if failed_job is not None:
                        failure_repo.mark_failed(failed_job, error_message=str(exc))
                        failure_session.commit()
                finally:
                    failure_session.close()
            raise
        finally:
            session.close()

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a synthetic Telegram update against the live Helly runtime without using the webhook endpoint."
    )
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument("--display-name", default="Synthetic User")
    parser.add_argument("--username", default=None)
    parser.add_argument("--language-code", default="en")
    parser.add_argument("--content-type", choices=("text", "contact"), default="text")
    parser.add_argument("--text", default=None)
    parser.add_argument("--contact-phone-number", default=None)
    parser.add_argument("--update-id", type=int, default=None)
    parser.add_argument("--message-id", type=int, default=1)
    parser.add_argument("--drain-worker-jobs", action="store_true")
    parser.add_argument("--max-worker-jobs", type=int, default=10)
    parser.add_argument("--deliver-notifications", action="store_true")
    args = parser.parse_args()

    if args.content_type == "text" and not args.text:
        raise SystemExit("--text is required for text updates")
    if args.content_type == "contact" and not args.contact_phone_number:
        raise SystemExit("--contact-phone-number is required for contact updates")

    settings = get_settings()
    configure_logging(settings.log_level)

    update_id = args.update_id or int(time.time_ns() // 1_000)
    telegram_chat_id = args.telegram_chat_id or args.telegram_user_id
    payload = _build_message_payload(
        update_id=update_id,
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        message_id=args.message_id,
        display_name=args.display_name,
        username=args.username,
        language_code=args.language_code,
        content_type=args.content_type,
        text=args.text,
        contact_phone_number=args.contact_phone_number,
    )
    normalized = normalize_telegram_update(payload)

    session_factory = get_session_factory()
    session = session_factory()
    try:
        result = TelegramUpdateService(session).process(normalized)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    worker_results: list[dict[str, Any]] = []
    if args.drain_worker_jobs:
        worker_results = _drain_worker_queue(
            max_jobs=args.max_worker_jobs,
            deliver_notifications=args.deliver_notifications,
        )

    snapshot = load_snapshot(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=telegram_chat_id,
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "normalized_content_type": normalized.content_type,
                "process_result": {
                    "status": result.status,
                    "deduplicated": result.deduplicated,
                    "notification_templates": result.notification_templates,
                    "user_id": result.user_id,
                },
                "worker_results": worker_results,
                "snapshot": {
                    "user_found": snapshot.user is not None,
                    "candidate_state": (snapshot.candidate_profile or {}).get("state"),
                    "vacancy_state": (snapshot.vacancy or {}).get("state"),
                    "match_status": (snapshot.invited_match or {}).get("status"),
                    "interview_state": (snapshot.interview_session or {}).get("state"),
                    "latest_notification": (snapshot.latest_notification or {}).get("template_key"),
                    "latest_transition": (
                        None
                        if snapshot.latest_state_transition is None
                        else {
                            "entity_type": snapshot.latest_state_transition.get("entity_type"),
                            "from_state": snapshot.latest_state_transition.get("from_state"),
                            "to_state": snapshot.latest_state_transition.get("to_state"),
                        }
                    ),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
