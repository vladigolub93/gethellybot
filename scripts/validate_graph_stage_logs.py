#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx


GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"

QUERY = """
query EnvironmentLogs($environmentId: String!, $afterLimit: Int) {
  environmentLogs(environmentId: $environmentId, afterLimit: $afterLimit) {
    message
    severity
    timestamp
    attributes {
      key
      value
    }
    tags {
      deploymentId
      serviceId
    }
  }
}
"""


def _fail(message: str, **payload: Any) -> None:
    print(json.dumps({"status": "failed", "message": message, **payload}, default=str, indent=2))
    raise SystemExit(1)


def _extract_attr(attrs: Any, key: str) -> str | None:
    if isinstance(attrs, dict):
        value = attrs.get(key)
        return None if value is None else str(value)
    if isinstance(attrs, list):
        for item in attrs:
            if isinstance(item, dict):
                item_key = item.get("key") or item.get("name")
                if item_key == key:
                    value = item.get("value")
                    return None if value is None else str(value)
    return None


def _matches(
    node: dict[str, Any],
    *,
    contains: str,
    expected_stage: str | None,
    expected_telegram_user_id: str | None,
) -> bool:
    message = str(node.get("message") or "")
    if contains not in message:
        return False

    attrs = node.get("attributes")
    if expected_stage is not None:
        stage_value = _extract_attr(attrs, "stage")
        if stage_value != expected_stage:
            return False

    if expected_telegram_user_id is not None:
        user_value = _extract_attr(attrs, "telegram_user_id")
        if user_value != expected_telegram_user_id:
            return False

    return True


def _fetch_logs(
    *,
    token: str,
    environment_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            GRAPHQL_URL,
            headers=headers,
            json={
                "query": QUERY,
                "variables": {
                    "environmentId": environment_id,
                    "afterLimit": limit,
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            _fail("railway_graphql_error", errors=payload["errors"])

    return (payload.get("data") or {}).get("environmentLogs") or []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate that Railway logs contain graph_stage_executed for the expected stage/user."
    )
    parser.add_argument("--contains", default="graph_stage_executed")
    parser.add_argument("--environment-id", default=os.getenv("RAILWAY_ENVIRONMENT_ID"))
    parser.add_argument("--token", default=os.getenv("RAILWAY_API_TOKEN"))
    parser.add_argument("--expect-stage")
    parser.add_argument("--expect-telegram-user-id")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--print-matches", action="store_true")
    args = parser.parse_args()

    if not args.token:
        _fail("missing_railway_api_token", env_var="RAILWAY_API_TOKEN")
    if not args.environment_id:
        _fail("missing_railway_environment_id", env_var="RAILWAY_ENVIRONMENT_ID")

    logs = _fetch_logs(
        token=args.token,
        environment_id=args.environment_id,
        limit=args.limit,
    )

    matches = [
        log
        for log in logs
        if _matches(
            log,
            contains=args.contains,
            expected_stage=args.expect_stage,
            expected_telegram_user_id=args.expect_telegram_user_id,
        )
    ]

    result = {
        "status": "ok" if matches else "failed",
        "environment_id": args.environment_id,
        "contains": args.contains,
        "expected_stage": args.expect_stage,
        "expected_telegram_user_id": args.expect_telegram_user_id,
        "scanned_logs": len(logs),
        "match_count": len(matches),
    }

    if not matches:
        print(json.dumps(result, default=str, indent=2))
        raise SystemExit(1)

    result["latest_match"] = matches[0] if not args.print_matches else None
    if args.print_matches:
        result["matches"] = matches

    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
