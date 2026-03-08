#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys


SCENARIOS: dict[str, list[str]] = {
    "candidate_summary_review_help": [
        "--expect-candidate-state",
        "SUMMARY_REVIEW",
        "--expect-inbound-contains",
        "How long",
        "--forbid-candidate-version-source-type",
        "summary_user_edit",
        "--expect-log-stage",
        "SUMMARY_REVIEW",
    ],
    "candidate_questions_clarification": [
        "--expect-candidate-state",
        "QUESTIONS_PENDING",
        "--expect-inbound-contains",
        "gross",
        "--expect-log-stage",
        "QUESTIONS_PENDING",
    ],
    "manager_vacancy_summary_review_help": [
        "--expect-vacancy-state",
        "VACANCY_SUMMARY_REVIEW",
        "--expect-inbound-contains",
        "How long",
        "--forbid-vacancy-version-source-type",
        "summary_user_edit",
        "--expect-log-stage",
        "VACANCY_SUMMARY_REVIEW",
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a predefined live smoke validation scenario for the remaining Phase L checks."
    )
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--railway-token", default=os.getenv("RAILWAY_API_TOKEN"))
    parser.add_argument("--railway-environment-id", default=os.getenv("RAILWAY_ENVIRONMENT_ID"))
    parser.add_argument("--allow-transition", action="store_true")
    args = parser.parse_args()

    command = [
        sys.executable,
        "scripts/validate_live_stage_checkpoint.py",
        "--telegram-user-id",
        str(args.telegram_user_id),
        *SCENARIOS[args.scenario],
    ]

    if args.railway_token:
        command.extend(["--railway-token", args.railway_token])
    if args.railway_environment_id:
        command.extend(["--railway-environment-id", args.railway_environment_id])
    if args.allow_transition:
        command.append("--allow-transition")

    raise SystemExit(subprocess.run(command, check=False).returncode)


if __name__ == "__main__":
    main()
