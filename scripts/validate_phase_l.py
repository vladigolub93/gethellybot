#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


SCENARIOS = (
    "candidate_summary_review_help",
    "candidate_questions_clarification",
    "manager_vacancy_summary_review_help",
)


def _run_scenario(
    *,
    python_bin: str,
    telegram_user_id: int,
    scenario: str,
    railway_token: str | None,
    railway_environment_id: str | None,
) -> dict[str, object]:
    command = [
        python_bin,
        "scripts/validate_live_smoke_scenario.py",
        "--telegram-user-id",
        str(telegram_user_id),
        "--scenario",
        scenario,
    ]
    if railway_token:
        command.extend(["--railway-token", railway_token])
    if railway_environment_id:
        command.extend(["--railway-environment-id", railway_environment_id])

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    payload: dict[str, object] = {
        "scenario": scenario,
        "exit_code": result.returncode,
    }
    output = (result.stdout or result.stderr or "").strip()
    if output:
        try:
            payload["details"] = json.loads(output)
        except json.JSONDecodeError:
            payload["details"] = output
    payload["status"] = "passed" if result.returncode == 0 else "failed"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all remaining Phase L live validation scenarios and report their status."
    )
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--railway-token", default=os.getenv("RAILWAY_API_TOKEN"))
    parser.add_argument("--railway-environment-id", default=os.getenv("RAILWAY_ENVIRONMENT_ID"))
    args = parser.parse_args()

    python_bin = sys.executable
    results = [
        _run_scenario(
            python_bin=python_bin,
            telegram_user_id=args.telegram_user_id,
            scenario=scenario,
            railway_token=args.railway_token,
            railway_environment_id=args.railway_environment_id,
        )
        for scenario in SCENARIOS
    ]

    passed = sum(1 for item in results if item["status"] == "passed")
    failed = len(results) - passed
    print(
        json.dumps(
            {
                "status": "ok" if failed == 0 else "partial",
                "telegram_user_id": args.telegram_user_id,
                "passed": passed,
                "failed": failed,
                "results": results,
            },
            default=str,
            indent=2,
        )
    )
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
