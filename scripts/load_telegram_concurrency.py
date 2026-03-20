#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import argparse
import itertools
import json
import threading
import time
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any
from unittest.mock import patch

import httpx
from sqlalchemy import func, select

from apps.api.main import app as fastapi_app
from scripts.reset_telegram_user import build_plan, reset_user
from src.config.logging import configure_logging
from src.config.settings import get_settings
from src.db.models.core import JobExecutionLog, Notification, RawMessage, User
from src.db.session import get_engine, get_session_factory
from src.integrations.telegram_bot import TelegramBotClient
from src.jobs.processor import process_job
from src.telegram.normalizer import normalize_telegram_update
from src.telegram.service import TelegramUpdateService


SCENARIOS: dict[str, list[str]] = {
    "start_only": ["/start"],
    "candidate_entry": ["/start", "Candidate"],
    "manager_entry": ["/start", "Hiring Manager"],
    "candidate_text": [
        "/start",
        "Candidate",
        "Senior backend engineer with 8 years in Python, FastAPI, Postgres, Redis, and AWS.",
    ],
}


@dataclass(frozen=True)
class MessageOutcome:
    telegram_user_id: int
    message_index: int
    text: str
    latency_ms: float
    status: str
    deduplicated: bool
    error: str | None


class TelegramOutboundStub:
    def __init__(self) -> None:
        self._message_ids = itertools.count(10_000_000)
        self._lock = threading.Lock()
        self.calls = 0
        self.per_chat_calls: Counter[int] = Counter()

    def build_message_result(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        reply_to_message_id: int | None = None,
    ) -> dict:
        with self._lock:
            message_id = next(self._message_ids)
            self.calls += 1
            self.per_chat_calls[int(chat_id)] += 1
        return {
            "message_id": message_id,
            "date": int(time.time()),
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
            "reply_markup": reply_markup,
            "reply_to_message_id": reply_to_message_id,
        }

    @staticmethod
    def build_callback_result(*, callback_query_id: str, text: str | None = None) -> dict:
        return {"ok": True, "callback_query_id": callback_query_id, "text": text}

    @staticmethod
    def build_file_result(*, telegram_file_id: str) -> dict:
        return {
            "file_id": telegram_file_id,
            "file_unique_id": f"stub-{telegram_file_id}",
            "file_path": f"stub/{telegram_file_id}",
        }

    @staticmethod
    def build_file_bytes(*, file_path: str) -> bytes:
        return f"stub:{file_path}".encode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a concurrent synthetic Telegram load test against the live Helly runtime."
    )
    parser.add_argument("--users", type=int, default=1000, help="How many synthetic users to simulate.")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Thread pool size. Defaults to the same value as --users.",
    )
    parser.add_argument(
        "--transport",
        choices=("service", "asgi", "http"),
        default="asgi",
        help="How to route synthetic updates. 'asgi' is closer to the real webhook path.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8010",
        help="Base URL for --transport http.",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS.keys()),
        default="candidate_entry",
        help="Predefined text scenario to replay for each user.",
    )
    parser.add_argument(
        "--messages-json",
        default="",
        help='Optional JSON array of messages. Overrides --scenario, for example \'["/start","Candidate"]\'.',
    )
    parser.add_argument(
        "--base-user-id",
        type=int,
        default=9_910_000_000,
        help="First synthetic telegram_user_id in the generated range.",
    )
    parser.add_argument(
        "--think-time-ms",
        type=int,
        default=0,
        help="Sleep between messages for the same synthetic user.",
    )
    parser.add_argument(
        "--stagger-ms",
        type=int,
        default=0,
        help="Optional stagger before each synthetic user starts.",
    )
    parser.add_argument(
        "--drain-worker-jobs",
        action="store_true",
        help="Drain queued jobs after the chat burst using the same processor logic as the worker.",
    )
    parser.add_argument(
        "--max-drain-jobs",
        type=int,
        default=5000,
        help="Safety cap when --drain-worker-jobs is enabled.",
    )
    parser.add_argument(
        "--deliver-notifications",
        action="store_true",
        help="When draining jobs, also deliver queued notification jobs.",
    )
    parser.add_argument(
        "--cleanup-before",
        action="store_true",
        help="Hard-delete any previously created synthetic users in the generated range before the run.",
    )
    parser.add_argument(
        "--cleanup-after",
        action="store_true",
        help="Hard-delete the synthetic users in the generated range after the run completes.",
    )
    parser.add_argument(
        "--no-stub-telegram-outbound",
        action="store_true",
        help="Do not stub Telegram outbound sends. Unsafe for real environments.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="Runtime log level during the load test. Default: WARNING.",
    )
    return parser.parse_args()


def _build_messages(args: argparse.Namespace) -> list[str]:
    if args.messages_json:
        payload = json.loads(args.messages_json)
        if not isinstance(payload, list) or not payload or not all(isinstance(value, str) for value in payload):
            raise SystemExit("--messages-json must be a non-empty JSON array of strings.")
        return [value.strip() for value in payload if value.strip()]
    return list(SCENARIOS[args.scenario])


def _build_message_payload(
    *,
    update_id: int,
    telegram_user_id: int,
    telegram_chat_id: int,
    message_id: int,
    display_name: str,
    username: str,
    text: str,
) -> dict[str, Any]:
    first_name, _, last_name = display_name.partition(" ")
    return {
        "update_id": update_id,
        "message": {
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
                "language_code": "en",
            },
            "text": text,
        },
    }


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return float(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight)


def _latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "min": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": round(float(ordered[0]), 2),
        "avg": round(float(mean(values)), 2),
        "p50": round(_percentile(ordered, 0.50), 2),
        "p95": round(_percentile(ordered, 0.95), 2),
        "p99": round(_percentile(ordered, 0.99), 2),
        "max": round(float(ordered[-1]), 2),
    }


def _job_status_counts(*, since_utc: datetime) -> dict[str, int]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        stmt = (
            select(JobExecutionLog.status, func.count())
            .where(JobExecutionLog.queued_at >= since_utc)
            .group_by(JobExecutionLog.status)
        )
        return {str(status): int(count) for status, count in session.execute(stmt).all()}
    finally:
        session.close()


def _range_db_counts(*, base_user_id: int, user_count: int) -> dict[str, int]:
    end_user_id = base_user_id + user_count - 1
    session_factory = get_session_factory()
    session = session_factory()
    try:
        users_stmt = select(User.id).where(User.telegram_user_id.between(base_user_id, end_user_id))
        user_ids = list(session.execute(users_stmt).scalars().all())
        user_count_value = len(user_ids)

        raw_messages_count = int(
            session.execute(
                select(func.count()).select_from(RawMessage).where(
                    RawMessage.telegram_chat_id.between(base_user_id, end_user_id)
                )
            ).scalar_one()
            or 0
        )

        if user_ids:
            notifications_count = int(
                session.execute(
                    select(func.count()).select_from(Notification).where(Notification.user_id.in_(user_ids))
                ).scalar_one()
                or 0
            )
        else:
            notifications_count = 0

        return {
            "users": user_count_value,
            "raw_messages": raw_messages_count,
            "notifications": notifications_count,
        }
    finally:
        session.close()


def _cleanup_generated_users(*, base_user_id: int, user_count: int) -> dict[str, Any]:
    end_user_id = base_user_id + user_count - 1
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(User.id, User.telegram_user_id).where(User.telegram_user_id.between(base_user_id, end_user_id))
        ).all()

    deleted_users = 0
    aggregate_counts: Counter[str] = Counter()
    for user_id, _telegram_user_id in rows:
        plan = build_plan(user_id=str(user_id))
        summary = reset_user(user_id=str(user_id), plan=plan)
        aggregate_counts.update(summary)
        deleted_users += 1

    return {
        "matched_users": len(rows),
        "deleted_users": deleted_users,
        "deleted_rows": dict(aggregate_counts),
    }


def _drain_worker_jobs(*, max_jobs: int, include_notifications: bool) -> dict[str, Any]:
    processed = 0
    statuses: Counter[str] = Counter()
    job_types: Counter[str] = Counter()
    session_factory = get_session_factory()

    for _ in range(max_jobs):
        session = session_factory()
        job = None
        try:
            stmt = select(JobExecutionLog).where(JobExecutionLog.status == "queued")
            if not include_notifications:
                stmt = stmt.where(~JobExecutionLog.job_type.like("notification_%"))
            stmt = stmt.order_by(JobExecutionLog.queued_at.asc()).limit(1).with_for_update(skip_locked=True)
            job = session.execute(stmt).scalar_one_or_none()
            if job is None:
                session.commit()
                break
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            session.flush()
            result = process_job(session, job)
            job.status = "completed"
            job.result_json = result
            job.finished_at = datetime.now(timezone.utc)
            session.commit()
            processed += 1
            statuses["completed"] += 1
            job_types[job.job_type] += 1
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            if job is not None:
                failure_session = session_factory()
                try:
                    failed = failure_session.get(JobExecutionLog, job.id)
                    if failed is not None:
                        failed.status = "failed"
                        failed.last_error = str(exc)[:4000]
                        failed.finished_at = datetime.now(timezone.utc)
                        failure_session.commit()
                finally:
                    failure_session.close()
                statuses["failed"] += 1
                job_types[job.job_type] += 1
            break
        finally:
            session.close()

    return {
        "processed_jobs": processed,
        "statuses": dict(statuses),
        "job_types": dict(job_types),
    }


def _run_user_sequence(
    *,
    user_index: int,
    base_user_id: int,
    messages: list[str],
    think_time_ms: int,
    stagger_ms: int,
    start_signal: threading.Event,
    update_id_seed: int,
) -> dict[str, Any]:
    telegram_user_id = base_user_id + user_index
    display_name = f"Synthetic Load {user_index:05d}"
    username = f"synthetic_load_{telegram_user_id}"
    outcomes: list[MessageOutcome] = []
    start_signal.wait()
    if stagger_ms > 0:
        time.sleep((stagger_ms * user_index) / 1000.0)
    user_started_at = time.perf_counter()
    session_factory = get_session_factory()

    for message_index, text in enumerate(messages, start=1):
        payload = _build_message_payload(
            update_id=update_id_seed + (user_index * 10_000) + message_index,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_user_id,
            message_id=message_index,
            display_name=display_name,
            username=username,
            text=text,
        )
        normalized = normalize_telegram_update(payload)
        session = session_factory()
        started_at = time.perf_counter()
        try:
            result = TelegramUpdateService(session).process(normalized)
            latency_ms = (time.perf_counter() - started_at) * 1000.0
            outcomes.append(
                MessageOutcome(
                    telegram_user_id=telegram_user_id,
                    message_index=message_index,
                    text=text,
                    latency_ms=latency_ms,
                    status=result.status,
                    deduplicated=result.deduplicated,
                    error=None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            latency_ms = (time.perf_counter() - started_at) * 1000.0
            outcomes.append(
                MessageOutcome(
                    telegram_user_id=telegram_user_id,
                    message_index=message_index,
                    text=text,
                    latency_ms=latency_ms,
                    status="exception",
                    deduplicated=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            break
        finally:
            session.close()
        if think_time_ms > 0 and message_index != len(messages):
            time.sleep(think_time_ms / 1000.0)

    return {
        "telegram_user_id": telegram_user_id,
        "duration_ms": round((time.perf_counter() - user_started_at) * 1000.0, 2),
        "outcomes": outcomes,
    }


async def _run_user_sequence_asgi(
    *,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    start_signal: asyncio.Event,
    user_index: int,
    base_user_id: int,
    messages: list[str],
    think_time_ms: int,
    stagger_ms: int,
    update_id_seed: int,
    webhook_secret: str,
) -> dict[str, Any]:
    telegram_user_id = base_user_id + user_index
    display_name = f"Synthetic Load {user_index:05d}"
    username = f"synthetic_load_{telegram_user_id}"
    outcomes: list[MessageOutcome] = []

    async with semaphore:
        await start_signal.wait()
        if stagger_ms > 0:
            await asyncio.sleep((stagger_ms * user_index) / 1000.0)
        user_started_at = time.perf_counter()

        for message_index, text in enumerate(messages, start=1):
            payload = _build_message_payload(
                update_id=update_id_seed + (user_index * 10_000) + message_index,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_user_id,
                message_id=message_index,
                display_name=display_name,
                username=username,
                text=text,
            )
            headers = {}
            if webhook_secret:
                headers["x-telegram-bot-api-secret-token"] = webhook_secret
            started_at = time.perf_counter()
            try:
                response = await client.post("/telegram/webhook", json=payload, headers=headers)
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                if response.status_code >= 400:
                    try:
                        error_payload = response.json()
                    except Exception:  # noqa: BLE001
                        error_payload = {"detail": response.text}
                    outcomes.append(
                        MessageOutcome(
                            telegram_user_id=telegram_user_id,
                            message_index=message_index,
                            text=text,
                            latency_ms=latency_ms,
                            status=f"http_{response.status_code}",
                            deduplicated=False,
                            error=str(error_payload.get("detail") or error_payload),
                        )
                    )
                    break
                result = response.json()
                outcomes.append(
                    MessageOutcome(
                        telegram_user_id=telegram_user_id,
                        message_index=message_index,
                        text=text,
                        latency_ms=latency_ms,
                        status=str(result.get("status") or "processed"),
                        deduplicated=bool(result.get("deduplicated")),
                        error=None,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                outcomes.append(
                    MessageOutcome(
                        telegram_user_id=telegram_user_id,
                        message_index=message_index,
                        text=text,
                        latency_ms=latency_ms,
                        status="exception",
                        deduplicated=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                break

            if think_time_ms > 0 and message_index != len(messages):
                await asyncio.sleep(think_time_ms / 1000.0)

    return {
        "telegram_user_id": telegram_user_id,
        "duration_ms": round((time.perf_counter() - user_started_at) * 1000.0, 2),
        "outcomes": outcomes,
    }


async def _run_asgi_load(
    *,
    users: int,
    max_workers: int,
    base_user_id: int,
    messages: list[str],
    think_time_ms: int,
    stagger_ms: int,
    update_id_seed: int,
    webhook_secret: str,
) -> list[dict[str, Any]]:
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        start_signal = asyncio.Event()
        semaphore = asyncio.Semaphore(max_workers)
        tasks = [
            asyncio.create_task(
                _run_user_sequence_asgi(
                    client=client,
                    semaphore=semaphore,
                    start_signal=start_signal,
                    user_index=user_index,
                    base_user_id=base_user_id,
                    messages=messages,
                    think_time_ms=think_time_ms,
                    stagger_ms=stagger_ms,
                    update_id_seed=update_id_seed,
                    webhook_secret=webhook_secret,
                )
            )
            for user_index in range(users)
        ]
        start_signal.set()
        return await asyncio.gather(*tasks)


async def _run_http_load(
    *,
    users: int,
    max_workers: int,
    base_user_id: int,
    messages: list[str],
    think_time_ms: int,
    stagger_ms: int,
    update_id_seed: int,
    webhook_secret: str,
    base_url: str,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        start_signal = asyncio.Event()
        semaphore = asyncio.Semaphore(max_workers)
        tasks = [
            asyncio.create_task(
                _run_user_sequence_asgi(
                    client=client,
                    semaphore=semaphore,
                    start_signal=start_signal,
                    user_index=user_index,
                    base_user_id=base_user_id,
                    messages=messages,
                    think_time_ms=think_time_ms,
                    stagger_ms=stagger_ms,
                    update_id_seed=update_id_seed,
                    webhook_secret=webhook_secret,
                )
            )
            for user_index in range(users)
        ]
        start_signal.set()
        return await asyncio.gather(*tasks)


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    configure_logging(args.log_level or settings.log_level)

    messages = _build_messages(args)
    users = int(args.users)
    max_workers = int(args.max_workers or args.users)
    start_utc = datetime.now(timezone.utc)

    if users <= 0:
        raise SystemExit("--users must be > 0")
    if max_workers <= 0:
        raise SystemExit("--max-workers must be > 0")

    cleanup_before_summary = None
    if args.cleanup_before:
        cleanup_before_summary = _cleanup_generated_users(base_user_id=args.base_user_id, user_count=users)

    before_counts = _range_db_counts(base_user_id=args.base_user_id, user_count=users)
    start_signal = threading.Event()
    update_id_seed = int(time.time_ns() // 1_000)
    user_results: list[dict[str, Any]] = []

    telegram_stub = TelegramOutboundStub()
    patches = []
    if not args.no_stub_telegram_outbound:
        def _fake_send_text_message(
            _client,
            *,
            chat_id: int,
            text: str,
            reply_markup: dict | None = None,
            reply_to_message_id: int | None = None,
        ) -> dict:
            return telegram_stub.build_message_result(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
            )

        def _fake_answer_callback_query(
            _client,
            *,
            callback_query_id: str,
            text: str | None = None,
        ) -> dict:
            return telegram_stub.build_callback_result(
                callback_query_id=callback_query_id,
                text=text,
            )

        def _fake_get_file(_client, *, telegram_file_id: str) -> dict:
            return telegram_stub.build_file_result(telegram_file_id=telegram_file_id)

        def _fake_download_file_bytes(_client, *, file_path: str) -> bytes:
            return telegram_stub.build_file_bytes(file_path=file_path)

        patches = [
            patch.object(TelegramBotClient, "send_text_message", _fake_send_text_message),
            patch.object(TelegramBotClient, "answer_callback_query", _fake_answer_callback_query),
            patch.object(TelegramBotClient, "get_file", _fake_get_file),
            patch.object(TelegramBotClient, "download_file_bytes", _fake_download_file_bytes),
        ]

    with ExitStack() as stack:
        for active_patch in patches:
            stack.enter_context(active_patch)

        overall_started_at = time.perf_counter()
        if args.transport == "service":
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(
                        _run_user_sequence,
                        user_index=user_index,
                        base_user_id=args.base_user_id,
                        messages=messages,
                        think_time_ms=args.think_time_ms,
                        stagger_ms=args.stagger_ms,
                        start_signal=start_signal,
                        update_id_seed=update_id_seed,
                    )
                    for user_index in range(users)
                ]
                start_signal.set()
                for future in futures:
                    user_results.append(future.result())
        elif args.transport == "asgi":
            user_results = asyncio.run(
                _run_asgi_load(
                    users=users,
                    max_workers=max_workers,
                    base_user_id=args.base_user_id,
                    messages=messages,
                    think_time_ms=args.think_time_ms,
                    stagger_ms=args.stagger_ms,
                    update_id_seed=update_id_seed,
                    webhook_secret=settings.telegram_webhook_secret,
                )
            )
        else:
            user_results = asyncio.run(
                _run_http_load(
                    users=users,
                    max_workers=max_workers,
                    base_user_id=args.base_user_id,
                    messages=messages,
                    think_time_ms=args.think_time_ms,
                    stagger_ms=args.stagger_ms,
                    update_id_seed=update_id_seed,
                    webhook_secret=settings.telegram_webhook_secret,
                    base_url=args.base_url.rstrip("/"),
                )
            )
        wall_time_ms = (time.perf_counter() - overall_started_at) * 1000.0

        drain_summary = None
        if args.drain_worker_jobs:
            drain_summary = _drain_worker_jobs(
                max_jobs=args.max_drain_jobs,
                include_notifications=args.deliver_notifications,
            )

    after_counts = _range_db_counts(base_user_id=args.base_user_id, user_count=users)
    cleanup_after_summary = None
    if args.cleanup_after:
        cleanup_after_summary = _cleanup_generated_users(base_user_id=args.base_user_id, user_count=users)

    all_outcomes = [outcome for user_result in user_results for outcome in user_result["outcomes"]]
    message_latencies = [outcome.latency_ms for outcome in all_outcomes]
    user_durations = [float(user_result["duration_ms"]) for user_result in user_results]
    status_counts = Counter(outcome.status for outcome in all_outcomes)
    deduplicated_count = sum(1 for outcome in all_outcomes if outcome.deduplicated)
    errors = Counter(outcome.error for outcome in all_outcomes if outcome.error)
    end_utc = datetime.now(timezone.utc)

    db_delta = {
        key: after_counts.get(key, 0) - before_counts.get(key, 0)
        for key in sorted(set(before_counts) | set(after_counts))
    }

    payload = {
        "status": "ok",
        "config": {
            "users": users,
            "max_workers": max_workers,
            "messages_per_user": len(messages),
            "scenario": args.scenario if not args.messages_json else "custom",
            "transport": args.transport,
            "messages": messages,
            "base_user_id": args.base_user_id,
            "think_time_ms": args.think_time_ms,
            "stagger_ms": args.stagger_ms,
            "telegram_outbound_stubbed": not args.no_stub_telegram_outbound,
            "drain_worker_jobs": bool(args.drain_worker_jobs),
            "deliver_notifications_during_drain": bool(args.deliver_notifications),
        },
        "run": {
            "started_at": start_utc.isoformat(),
            "finished_at": end_utc.isoformat(),
            "wall_time_ms": round(wall_time_ms, 2),
            "throughput_messages_per_second": round(
                len(all_outcomes) / max(wall_time_ms / 1000.0, 0.001),
                2,
            ),
        },
        "results": {
            "message_status_counts": dict(status_counts),
            "deduplicated_messages": deduplicated_count,
            "message_latency_ms": _latency_summary(message_latencies),
            "user_duration_ms": _latency_summary(user_durations),
            "error_count": sum(errors.values()),
            "top_errors": [{"error": error, "count": count} for error, count in errors.most_common(10)],
        },
        "db_counts_before": before_counts,
        "db_counts_after": after_counts,
        "db_delta": db_delta,
        "job_status_counts_since_start": _job_status_counts(since_utc=start_utc),
        "telegram_outbound": {
            "stubbed": not args.no_stub_telegram_outbound,
            "message_calls": telegram_stub.calls if not args.no_stub_telegram_outbound else None,
            "unique_chats_touched": len(telegram_stub.per_chat_calls) if not args.no_stub_telegram_outbound else None,
        },
        "cleanup_before": cleanup_before_summary,
        "cleanup_after": cleanup_after_summary,
        "drain_summary": drain_summary,
    }

    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
