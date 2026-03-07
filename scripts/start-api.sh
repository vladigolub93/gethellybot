#!/usr/bin/env bash
set -euo pipefail

PORT_VALUE="${PORT:-${API_PORT:-8000}}"
HOST_VALUE="${API_HOST:-0.0.0.0}"

alembic upgrade head
exec uvicorn apps.api.main:app --host "${HOST_VALUE}" --port "${PORT_VALUE}"
