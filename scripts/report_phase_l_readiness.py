#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


SCENARIOS: dict[str, dict[str, object]] = {
    "candidate_summary_review_help": {
        "stage": "SUMMARY_REVIEW",
        "requires_railway_logs": True,
        "requires_real_user_input": True,
    },
    "candidate_questions_clarification": {
        "stage": "QUESTIONS_PENDING",
        "requires_railway_logs": True,
        "requires_real_user_input": True,
    },
    "manager_vacancy_summary_review_help": {
        "stage": "VACANCY_SUMMARY_REVIEW",
        "requires_railway_logs": True,
        "requires_real_user_input": True,
    },
}


def _get_webhook_info(token: str) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode())
            return payload.get("result") if payload.get("ok") else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app_base_url = os.getenv("VALIDATION_APP_BASE_URL") or os.getenv("APP_BASE_URL")
    railway_token = os.getenv("RAILWAY_API_TOKEN")
    railway_environment_id = os.getenv("RAILWAY_ENVIRONMENT_ID")
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")

    webhook_info = _get_webhook_info(token) if token else None

    blockers: list[str] = []
    if not token:
        blockers.append("TELEGRAM_BOT_TOKEN is missing")
    if not app_base_url:
        blockers.append("VALIDATION_APP_BASE_URL or APP_BASE_URL is missing")
    elif "localhost" in app_base_url or "127.0.0.1" in app_base_url:
        blockers.append("APP_BASE_URL points to localhost; set VALIDATION_APP_BASE_URL to the Railway API domain")
    if not railway_token:
        blockers.append("RAILWAY_API_TOKEN is missing")
    if not railway_environment_id:
        blockers.append("RAILWAY_ENVIRONMENT_ID is missing")
    if not webhook_secret:
        blockers.append("TELEGRAM_WEBHOOK_SECRET is not available locally, so synthetic webhook posts cannot be replayed from this environment")

    can_validate_after_real_input = (
        bool(token)
        and bool(app_base_url)
        and "localhost" not in (app_base_url or "")
        and "127.0.0.1" not in (app_base_url or "")
        and bool(railway_token)
        and bool(railway_environment_id)
    )
    can_drive_synthetic_posts = can_validate_after_real_input and bool(webhook_secret)

    scenario_readiness: dict[str, object] = {}
    for scenario_name, scenario_meta in SCENARIOS.items():
        scenario_blockers: list[str] = []
        if scenario_meta["requires_real_user_input"] and not can_validate_after_real_input:
            scenario_blockers.append("missing prerequisites for post-message validation")
        if scenario_meta["requires_railway_logs"] and not railway_token:
            scenario_blockers.append("RAILWAY_API_TOKEN is missing")
        if scenario_meta["requires_railway_logs"] and not railway_environment_id:
            scenario_blockers.append("RAILWAY_ENVIRONMENT_ID is missing")
        scenario_readiness[scenario_name] = {
            "stage": scenario_meta["stage"],
            "status": "ready" if not scenario_blockers else "blocked",
            "requires_real_user_input": scenario_meta["requires_real_user_input"],
            "blockers": scenario_blockers,
        }

    status = "ready" if not blockers else "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "app_base_url": app_base_url,
                "has_telegram_bot_token": bool(token),
                "has_railway_api_token": bool(railway_token),
                "has_railway_environment_id": bool(railway_environment_id),
                "has_webhook_secret_locally": bool(webhook_secret),
                "can_validate_after_real_user_input": can_validate_after_real_input,
                "can_drive_synthetic_webhook_posts": can_drive_synthetic_posts,
                "webhook_info": webhook_info,
                "blockers": blockers,
                "scenario_readiness": scenario_readiness,
            },
            indent=2,
        )
    )

    raise SystemExit(0 if not blockers else 1)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
