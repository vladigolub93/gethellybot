#!/usr/bin/env bash
set -euo pipefail

export HELLY_PROCESS_TYPE="api"

PORT_VALUE="${PORT:-${API_PORT:-8000}}"
HOST_VALUE="${API_HOST:-0.0.0.0}"
APP_ENV_VALUE="${APP_ENV:-development}"
WORKERS_VALUE="${API_WORKERS:-${WEB_CONCURRENCY:-}}"

if [[ -z "${WORKERS_VALUE}" ]]; then
  if [[ "${APP_ENV_VALUE}" == "production" ]]; then
    if [[ "${TELEGRAM_ENQUEUE_UPDATES_ENABLED:-0}" == "1" ]]; then
      WORKERS_VALUE="1"
    else
      WORKERS_VALUE="2"
    fi
  else
    WORKERS_VALUE="1"
  fi
fi

alembic upgrade head
exec uvicorn apps.api.main:app --host "${HOST_VALUE}" --port "${PORT_VALUE}" --workers "${WORKERS_VALUE}"
