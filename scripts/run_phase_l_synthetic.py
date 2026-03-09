#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from apps.worker.main import _process_job
from scripts.inspect_telegram_user import Snapshot, load_snapshot
from scripts.reset_telegram_user import build_plan, reset_user
from src.config.settings import get_settings
from src.db.models.core import JobExecutionLog
from src.db.repositories.job_execution_logs import JobExecutionLogsRepository
from src.db.session import get_session_factory


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Tester:
    telegram_user_id: int
    display_name: str
    username: str


CANDIDATE_SUMMARY_TESTER = Tester(991100101, "Synthetic Candidate Summary", "synthetic_candidate_summary")
CANDIDATE_QUESTIONS_TESTER = Tester(991100102, "Synthetic Candidate Questions", "synthetic_candidate_questions")
MANAGER_SUMMARY_TESTER = Tester(991100103, "Synthetic Manager Summary", "synthetic_manager_summary")


def _python_bin() -> str:
    return sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DB_USE_NULL_POOL", "1")
    return env


def _extract_replay_payload(output: str) -> dict[str, Any]:
    marker = '{\n  "status": "ok"'
    index = output.rfind(marker)
    if index == -1:
        raise RuntimeError(f"Could not find replay JSON payload in output:\n{output}")
    return json.loads(output[index:])


def _run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{output}")
    return output


def _reset_tester(tester: Tester) -> dict[str, Any]:
    snapshot = load_snapshot(telegram_user_id=tester.telegram_user_id, telegram_chat_id=None)
    if snapshot.user is None:
        return {"status": "not_found"}
    plan = build_plan(user_id=snapshot.user["id"])
    summary = reset_user(user_id=snapshot.user["id"], plan=plan)
    return {"status": "reset", "summary": summary}


def _replay_text(
    tester: Tester,
    text: str,
) -> tuple[dict[str, Any], str]:
    command = [
        _python_bin(),
        "scripts/replay_telegram_update.py",
        "--telegram-user-id",
        str(tester.telegram_user_id),
        "--display-name",
        tester.display_name,
        "--username",
        tester.username,
        "--text",
        text,
    ]
    output = _run_command(command)
    return _extract_replay_payload(output), output


def _assert_graph_log(output: str, stage: str, tester: Tester) -> None:
    if "graph_stage_executed" not in output or f'"stage": "{stage}"' not in output:
        raise RuntimeError(f"Missing graph_stage_executed log for stage {stage} in output:\n{output}")
    if f'"telegram_user_id": {tester.telegram_user_id}' not in output:
        raise RuntimeError(f"Missing telegram_user_id {tester.telegram_user_id} in graph log output:\n{output}")


def _snapshot(tester: Tester) -> Snapshot:
    return load_snapshot(telegram_user_id=tester.telegram_user_id, telegram_chat_id=None)


def _drain_entity_jobs(*, entity_type: str, entity_id: str, max_jobs: int = 10) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    processed: list[dict[str, Any]] = []

    for _ in range(max_jobs):
        session = session_factory()
        try:
            repo = JobExecutionLogsRepository(session)
            stmt = (
                select(JobExecutionLog)
                .where(
                    JobExecutionLog.status == "queued",
                    JobExecutionLog.entity_type == entity_type,
                    JobExecutionLog.entity_id == entity_id,
                )
                .order_by(JobExecutionLog.queued_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = session.execute(stmt).scalar_one_or_none()
            if job is None:
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
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return processed


def _candidate_summary_review_help() -> dict[str, Any]:
    tester = CANDIDATE_SUMMARY_TESTER
    _reset_tester(tester)
    _replay_text(tester, "/start")
    _replay_text(tester, "Candidate")
    _replay_text(
        tester,
        "Senior backend engineer. 8 years with Python, Django, FastAPI, Postgres, Redis, Docker, and AWS. Built APIs, internal platforms, and async jobs.",
    )
    snapshot = _snapshot(tester)
    candidate_version = snapshot.candidate_version or {}
    _drain_entity_jobs(
        entity_type="candidate_profile_version",
        entity_id=str(candidate_version["id"]),
        max_jobs=10,
    )
    _, help_output = _replay_text(tester, "How long will this take?")
    _assert_graph_log(help_output, "SUMMARY_REVIEW", tester)

    snapshot = _snapshot(tester)
    candidate = snapshot.candidate_profile or {}
    version = snapshot.candidate_version or {}
    latest_inbound = snapshot.latest_raw_message or {}

    if candidate.get("state") != "SUMMARY_REVIEW":
        raise RuntimeError(f"Expected SUMMARY_REVIEW, got {candidate.get('state')}")
    if version.get("source_type") == "summary_user_edit":
        raise RuntimeError("Help message incorrectly created summary_user_edit version")
    if "How long" not in ((latest_inbound.get("text_content") or "")):
        raise RuntimeError("Latest inbound message mismatch for candidate summary review help")

    return {
        "scenario": "candidate_summary_review_help",
        "telegram_user_id": tester.telegram_user_id,
        "candidate_state": candidate.get("state"),
        "latest_notification": (snapshot.latest_notification or {}).get("template_key"),
        "candidate_version_source_type": version.get("source_type"),
    }


def _candidate_questions_clarification() -> dict[str, Any]:
    tester = CANDIDATE_QUESTIONS_TESTER
    _reset_tester(tester)
    _replay_text(tester, "/start")
    _replay_text(tester, "Candidate")
    _replay_text(
        tester,
        "Backend engineer with 6 years in Python, FastAPI, Celery, Postgres, Redis, and AWS. Built B2B SaaS and internal tooling.",
    )
    snapshot = _snapshot(tester)
    candidate_version = snapshot.candidate_version or {}
    _drain_entity_jobs(
        entity_type="candidate_profile_version",
        entity_id=str(candidate_version["id"]),
        max_jobs=10,
    )
    _replay_text(tester, "Approve summary")
    _, help_output = _replay_text(tester, "Gross or net?")
    _assert_graph_log(help_output, "QUESTIONS_PENDING", tester)

    snapshot = _snapshot(tester)
    candidate = snapshot.candidate_profile or {}
    latest_inbound = snapshot.latest_raw_message or {}

    if candidate.get("state") != "QUESTIONS_PENDING":
        raise RuntimeError(f"Expected QUESTIONS_PENDING, got {candidate.get('state')}")
    if "Gross or net" not in ((latest_inbound.get("text_content") or "")):
        raise RuntimeError("Latest inbound message mismatch for candidate questions clarification")

    return {
        "scenario": "candidate_questions_clarification",
        "telegram_user_id": tester.telegram_user_id,
        "candidate_state": candidate.get("state"),
        "latest_notification": (snapshot.latest_notification or {}).get("template_key"),
    }


def _manager_vacancy_summary_review() -> dict[str, Any]:
    tester = MANAGER_SUMMARY_TESTER
    _reset_tester(tester)
    _replay_text(tester, "/start")
    _replay_text(tester, "Hiring Manager")
    _replay_text(
        tester,
        (
            "We are hiring a Senior Backend Engineer for a B2B SaaS platform. "
            "Main stack: Python, FastAPI, Postgres, Redis, Docker, AWS. "
            "Need someone to own APIs, async processing, and architecture. "
            "Remote in Europe. Budget 6000-7500 EUR gross."
        ),
    )
    snapshot = _snapshot(tester)
    vacancy_version = snapshot.vacancy_version or {}
    _drain_entity_jobs(
        entity_type="vacancy_version",
        entity_id=str(vacancy_version["id"]),
        max_jobs=10,
    )
    _, help_output = _replay_text(tester, "How long will this take?")
    _assert_graph_log(help_output, "VACANCY_SUMMARY_REVIEW", tester)

    snapshot = _snapshot(tester)
    vacancy = snapshot.vacancy or {}
    version = snapshot.vacancy_version or {}
    if vacancy.get("state") != "VACANCY_SUMMARY_REVIEW":
        raise RuntimeError(f"Expected VACANCY_SUMMARY_REVIEW after help, got {vacancy.get('state')}")
    if version.get("source_type") == "summary_user_edit":
        raise RuntimeError("Help message incorrectly created vacancy summary_user_edit version")

    _replay_text(
        tester,
        "Change the summary: this role is backend-focused, not full-stack. Please reflect Python backend ownership clearly.",
    )
    snapshot = _snapshot(tester)
    vacancy_version = snapshot.vacancy_version or {}
    _drain_entity_jobs(
        entity_type="vacancy_version",
        entity_id=str(vacancy_version["id"]),
        max_jobs=10,
    )
    snapshot = _snapshot(tester)
    vacancy = snapshot.vacancy or {}
    version = snapshot.vacancy_version or {}
    if vacancy.get("state") != "VACANCY_SUMMARY_REVIEW":
        raise RuntimeError(f"Expected VACANCY_SUMMARY_REVIEW after correction, got {vacancy.get('state')}")
    if version.get("source_type") != "summary_user_edit":
        raise RuntimeError("Expected summary_user_edit version after explicit correction")

    _, approve_output = _replay_text(tester, "Approve summary")
    _assert_graph_log(approve_output, "VACANCY_SUMMARY_REVIEW", tester)
    snapshot = _snapshot(tester)
    vacancy = snapshot.vacancy or {}
    if vacancy.get("state") != "CLARIFICATION_QA":
        raise RuntimeError(f"Expected CLARIFICATION_QA after approval, got {vacancy.get('state')}")

    return {
        "scenario": "manager_vacancy_summary_review",
        "telegram_user_id": tester.telegram_user_id,
        "vacancy_state": vacancy.get("state"),
        "latest_notification": (snapshot.latest_notification or {}).get("template_key"),
        "vacancy_version_source_type": (snapshot.vacancy_version or {}).get("source_type"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the remaining Phase L smoke scenarios synthetically through the live Helly runtime."
    )
    parser.add_argument(
        "--scenario",
        choices=("candidate_summary_review_help", "candidate_questions_clarification", "manager_vacancy_summary_review", "all"),
        default="all",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required")

    results: list[dict[str, Any]] = []
    scenarios = (
        [args.scenario]
        if args.scenario != "all"
        else [
            "candidate_summary_review_help",
            "candidate_questions_clarification",
            "manager_vacancy_summary_review",
        ]
    )

    for scenario in scenarios:
        if scenario == "candidate_summary_review_help":
            results.append(_candidate_summary_review_help())
        elif scenario == "candidate_questions_clarification":
            results.append(_candidate_questions_clarification())
        elif scenario == "manager_vacancy_summary_review":
            results.append(_manager_vacancy_summary_review())

    print(json.dumps({"status": "ok", "results": results}, indent=2))


if __name__ == "__main__":
    main()
