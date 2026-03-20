# Telegram Concurrency Remediation Plan

## Goal

Reach a stable baseline of `100` simultaneous Telegram users for light text flows before attempting heavier mixed scenarios or `1000+` concurrency.

## What is already true

- The webhook no longer has to process the full Telegram update inline.
- With `TELEGRAM_ENQUEUE_UPDATES_ENABLED=1`, the webhook can acknowledge `100` concurrent `/start` requests without `500`.
- The remaining bottleneck is no longer request correctness, but queue-drain throughput and database connection limits.

## Current hard blocker

The current Supabase/Postgres connection endpoint behaves like a session-mode pooler with a hard max client ceiling. Under burst load this causes:

- `psycopg.OperationalError: MaxClientsInSessionMode: max clients reached`
- SQLAlchemy `QueuePool` timeouts when multiple worker processes compete for the same tiny pool

This means API and worker cannot safely share the same DB connection strategy.

## Architecture change introduced in code

The app now supports process-specific DB settings via:

- `HELLY_PROCESS_TYPE=api|worker|scheduler`
- `API_SUPABASE_DB_URL`
- `WORKER_SUPABASE_DB_URL`
- `SCHEDULER_SUPABASE_DB_URL`
- `API_DB_USE_NULL_POOL`
- `WORKER_DB_USE_NULL_POOL`
- `SCHEDULER_DB_USE_NULL_POOL`
- `API_DB_POOL_SIZE`
- `WORKER_DB_POOL_SIZE`
- `SCHEDULER_DB_POOL_SIZE`
- `API_DB_POOL_MAX_OVERFLOW`
- `WORKER_DB_POOL_MAX_OVERFLOW`
- `SCHEDULER_DB_POOL_MAX_OVERFLOW`
- `API_DB_POOL_TIMEOUT_SECONDS`
- `WORKER_DB_POOL_TIMEOUT_SECONDS`
- `SCHEDULER_DB_POOL_TIMEOUT_SECONDS`

This allows API and worker to use different DB modes without changing application logic.

## Recommended next infra layout

### API

Use a conservative, connection-reusing setup:

- `HELLY_PROCESS_TYPE=api`
- `API_WORKERS=1`
- `TELEGRAM_ENQUEUE_UPDATES_ENABLED=1`
- `API_DB_POOL_SIZE=1`
- `API_DB_POOL_MAX_OVERFLOW=0`
- `API_DB_POOL_TIMEOUT_SECONDS=30`
- `API_DB_USE_NULL_POOL=0`

Rationale:

- best measured `ack` latency among tested configurations
- avoids amplifying session-mode connection pressure

### Worker

Use a separate DB connection strategy from API:

- `HELLY_PROCESS_TYPE=worker`
- `WORKER_CONCURRENCY=4` only after DB endpoint supports it
- `WORKER_DB_USE_NULL_POOL=1` when using a worker-safe DB endpoint

Best option:

- point `WORKER_SUPABASE_DB_URL` to a DB endpoint better suited for burst job consumers
- keep API and worker on different connection configs

### Scheduler

Keep it conservative:

- `HELLY_PROCESS_TYPE=scheduler`
- `SCHEDULER_DB_POOL_SIZE=1`
- `SCHEDULER_DB_POOL_MAX_OVERFLOW=0`

## Rollout sequence

1. Keep async Telegram queue enabled.
2. Set process-specific DB env vars on Railway.
3. Move worker to a DB endpoint/config that does not hit session-mode max clients under parallel drain.
4. Deploy API with `1` worker.
5. Deploy worker with explicit `WORKER_CONCURRENCY`.
6. Re-run canaries:
   - `20 concurrent /start`
   - `50 concurrent /start`
   - `100 concurrent /start`
7. After `100` light-flow passes, run:
   - `100 concurrent candidate_entry`
   - `100 concurrent mixed text flow`

## Success criteria for the next stage

For `100 concurrent /start`:

- `0` HTTP `500`
- `100/100` webhook acks
- `100/100` queued jobs processed
- `100` users created
- `100` bot replies generated
- no DB max-client failures

## Non-goals for now

Do not target `1000` concurrent users yet.

That number is not useful until:

- `100 concurrent` is stable end-to-end
- worker throughput is verified under burst
- DB connection mode is fixed
