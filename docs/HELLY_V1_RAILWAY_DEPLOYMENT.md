# HELLY v1 Railway Deployment

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document defines the recommended Railway deployment shape for Helly v1.

It is aligned with the current codebase:

- `FastAPI` API service
- background `worker`
- background `scheduler`
- `Supabase Postgres`
- `Supabase Storage`
- `Telegram Bot API`

## 2. Deployment Shape

Create 3 Railway services from the same repository:

- `helly-api`
- `helly-worker`
- `helly-scheduler`

All 3 services should use the same environment variables.

Only `helly-api` needs public networking.

## 3. Build Strategy

Use the repository `Dockerfile` at project root.

This repository also includes service-specific Railway config-as-code files:

- `/deploy/railway/api.railway.json`
- `/deploy/railway/worker.railway.json`
- `/deploy/railway/scheduler.railway.json`

Per Railway docs, each service can point to its own custom config file path in service settings.

## 4. Service Config Paths

Recommended custom config file path per Railway service:

- `helly-api` -> `/deploy/railway/api.railway.json`
- `helly-worker` -> `/deploy/railway/worker.railway.json`
- `helly-scheduler` -> `/deploy/railway/scheduler.railway.json`

These files define builder, start command, and restart policy.

## 5. Start Commands

For `helly-api`:

```bash
bash scripts/start-api.sh
```

For `helly-worker`:

```bash
bash scripts/start-worker.sh
```

For `helly-scheduler`:

```bash
bash scripts/start-scheduler.sh
```

## 6. API Service Settings

Recommended Railway settings for `helly-api`:

- public networking enabled
- health check path: `/health`
- one replica is sufficient for the current baseline

`scripts/start-api.sh` runs:

1. `alembic upgrade head`
2. `uvicorn apps.api.main:app`

This is acceptable for the current single-instance baseline.

## 7. Required Environment Variables

Set these in Railway for all services:

- `APP_ENV=production`
- `APP_NAME=helly`
- `APP_LOG_LEVEL=INFO`
- `APP_BASE_URL=https://<railway-api-domain>`
- `API_HOST=0.0.0.0`
- `TELEGRAM_BOT_TOKEN=<bot-token>`
- `TELEGRAM_WEBHOOK_SECRET=<random-secret>`
- `OPENAI_API_KEY=<openai-key>`
- `OPENAI_MODEL_EXTRACTION=gpt-4.1-mini`
- `OPENAI_MODEL_REASONING=gpt-4.1`
- `SUPABASE_URL=https://pnuxbvtkkdlwxafvurze.supabase.co`
- `SUPABASE_DB_URL=<session-pooler-dsn with postgresql+psycopg://>`
- `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
- `SUPABASE_STORAGE_BUCKET_PRIVATE=helly-private`
- `QUEUE_BACKEND=database`
- `WORKER_POLL_INTERVAL_SECONDS=5`
- `SCHEDULER_POLL_INTERVAL_SECONDS=15`

Notes:

- Railway injects `PORT` automatically for the public API service.
- `SUPABASE_DB_URL` should use the session pooler DSN.
- For SQLAlchemy, the DSN should start with `postgresql+psycopg://`.

## 8. Recommended DSN Format

Example:

```txt
postgresql+psycopg://postgres.<project-ref>:<password>@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
```

## 9. Deploy Procedure

1. Create the 3 Railway services from the same GitHub repository.
2. For each service, set the custom config file path to the matching file in `/deploy/railway/`.
3. Confirm all 3 services build from the root `Dockerfile`.
4. Add the shared environment variables to all 3 services.
5. Deploy `helly-api`.
6. Confirm `/health` returns `200`.
7. Deploy `helly-worker`.
8. Deploy `helly-scheduler`.

## 10. Telegram Webhook Setup

After `helly-api` is deployed and has a public domain:

1. Set `APP_BASE_URL` to the Railway domain of `helly-api`
2. Configure the Telegram webhook

Example:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<railway-api-domain>/telegram/webhook",
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
  }'
```

To verify:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

## 11. Smoke Test Checklist

After deploy:

1. Open the bot in Telegram and send `/start`
2. Share contact
3. Reply `I agree`
4. Choose `Candidate`
5. Send a short text CV
6. Confirm a notification is returned from the live bot
7. Confirm `raw_messages`, `notifications`, and `job_execution_logs` are populated in Supabase

## 12. Operational Notes

- outbound Telegram delivery is asynchronous via the scheduler and worker
- Telegram media storage sync is asynchronous via the scheduler and worker
- the current queue backend is Postgres-backed
- if worker throughput becomes insufficient, scale `helly-worker` first

## 13. What Is Still Manual

Current deployment still requires manual actions in Railway:

- creating the 3 services
- assigning environment variables
- enabling the API public domain
- configuring the Telegram webhook

This is acceptable for the current v1 baseline.
