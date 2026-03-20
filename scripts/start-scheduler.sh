#!/usr/bin/env bash
set -euo pipefail

export HELLY_PROCESS_TYPE="scheduler"

exec python -m apps.scheduler.main
