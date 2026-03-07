#!/usr/bin/env bash
set -euo pipefail

PROCESS_TYPE="${HELLY_PROCESS_TYPE:-api}"

case "${PROCESS_TYPE}" in
  api)
    exec bash scripts/start-api.sh
    ;;
  worker)
    exec bash scripts/start-worker.sh
    ;;
  scheduler)
    exec bash scripts/start-scheduler.sh
    ;;
  *)
    echo "Unsupported HELLY_PROCESS_TYPE: ${PROCESS_TYPE}" >&2
    exit 1
    ;;
esac
