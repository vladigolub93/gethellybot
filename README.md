# Helly

Helly is a Telegram-first AI recruitment platform.

## Repository Status

This repository now contains:

- working product and architecture documentation
- backend baseline implementation
- Alembic migrations
- Telegram webhook intake
- candidate and vacancy onboarding flows
- matching and direct-contact foundations
- dormant interview and evaluation foundations for future premium modes
- Supabase and Telegram integration baseline
- Railway deployment baseline

## Start Here

- [docs/HELLY_V1_DIRECT_CONTACT_MATCHING_FLOW.md](/Users/vladigolub/Desktop/gethellybot/docs/HELLY_V1_DIRECT_CONTACT_MATCHING_FLOW.md)
- [docs/README.md](/Users/vladigolub/Desktop/gethellybot/docs/README.md)
- [docs/HELLY_V1_PROJECT_ARCHITECTURE.md](/Users/vladigolub/Desktop/gethellybot/docs/HELLY_V1_PROJECT_ARCHITECTURE.md)
- [docs/HELLY_V1_MASTER_TASK_LIST.md](/Users/vladigolub/Desktop/gethellybot/docs/HELLY_V1_MASTER_TASK_LIST.md)
- [docs/HELLY_V1_RAILWAY_DEPLOYMENT.md](/Users/vladigolub/Desktop/gethellybot/docs/HELLY_V1_RAILWAY_DEPLOYMENT.md)

## Local Commands

Local host execution now assumes `Python 3.12+`.

The canonical local/runtime-compatible path is Docker, because production also runs in Docker on `python:3.12-slim` with `langgraph` installed from project dependencies.

```bash
make run-api
make run-worker
make run-scheduler
make test
make db-upgrade
make docker-build
make docker-test
```

## Deploy Commands

Railway service start commands:

```bash
bash scripts/start-api.sh
bash scripts/start-worker.sh
bash scripts/start-scheduler.sh
```

## CV Challenge Launch Modes

Helly CV Challenge keeps the same HTML5 runtime and supports 2 launch transports:

- fallback mode: Telegram `web_app` button to `/webapp/cv-challenge`
- preferred mode: Telegram Game via `sendGame`

To enable Telegram Game transport, set:

```bash
TELEGRAM_CV_CHALLENGE_GAME_SHORT_NAME=<botfather_game_short_name>
```

If this env var is empty, Helly automatically falls back to the old WebApp button flow.
