#!/usr/bin/env bash
set -euo pipefail

VALIDATION_BASE_URL="${VALIDATION_APP_BASE_URL:-${APP_BASE_URL:-}}"

if [[ -z "${VALIDATION_BASE_URL:-}" ]]; then
  echo "VALIDATION_APP_BASE_URL or APP_BASE_URL is required" >&2
  exit 1
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "TELEGRAM_BOT_TOKEN is required" >&2
  exit 1
fi

EXPECTED_WEBHOOK_URL="${VALIDATION_BASE_URL%/}/telegram/webhook"

HEALTH_BODY="$(curl -fsS "${VALIDATION_BASE_URL%/}/health")"

python3 - "$HEALTH_BODY" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload.get("status") != "ok":
    raise SystemExit("Health check did not return status=ok")
print("health: ok")
PY

WEBHOOK_BODY="$(curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo")"

python3 - "$WEBHOOK_BODY" "$EXPECTED_WEBHOOK_URL" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expected_url = sys.argv[2]

if not payload.get("ok"):
    raise SystemExit("Telegram getWebhookInfo returned ok=false")

result = payload.get("result") or {}
actual_url = result.get("url")
if actual_url != expected_url:
    raise SystemExit(f"Webhook URL mismatch: expected {expected_url}, got {actual_url}")

print("webhook: ok")
print(f"pending_updates: {result.get('pending_update_count', 0)}")
if result.get("last_error_message"):
    print(f"last_error: {result['last_error_message']}")
PY
