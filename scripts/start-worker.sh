#!/usr/bin/env bash
set -euo pipefail

export HELLY_PROCESS_TYPE="worker"

CONCURRENCY_VALUE="${WORKER_CONCURRENCY:-}"
APP_ENV_VALUE="${APP_ENV:-development}"

if [[ -z "${CONCURRENCY_VALUE}" ]]; then
  CONCURRENCY_VALUE="1"
fi

if [[ "${CONCURRENCY_VALUE}" -le 1 ]]; then
  exec python -m apps.worker.main
fi

pids=()

terminate_children() {
  for pid in "${pids[@]:-}"; do
    kill "${pid}" 2>/dev/null || true
  done
  wait "${pids[@]:-}" 2>/dev/null || true
}

trap terminate_children INT TERM EXIT

for ((i = 1; i <= CONCURRENCY_VALUE; i++)); do
  python -m apps.worker.main &
  pids+=("$!")
done

exit_code=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    exit_code=$?
  fi
done
terminate_children
exit "${exit_code}"
