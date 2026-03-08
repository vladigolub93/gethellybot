# HELLY v1 Live Smoke Runbook

Version: 1.0  
Date: 2026-03-08

## 1. Purpose

This runbook defines the live manual smoke checks for the graph-owned Helly runtime on Railway + Supabase + Telegram.

It should be used together with:

- [HELLY_V1_RAILWAY_DEPLOYMENT.md](./HELLY_V1_RAILWAY_DEPLOYMENT.md)
- [HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md](./HELLY_V1_AGENT_OWNED_STAGE_REBUILD_PLAN.md)
- [HELLY_V1_IMPLEMENTATION_STATUS.md](./HELLY_V1_IMPLEMENTATION_STATUS.md)

## 2. Preconditions

Before running live smoke checks:

1. `make validate-production` must pass.
2. If local `.env` points `APP_BASE_URL` at localhost, export `VALIDATION_APP_BASE_URL=https://<railway-api-domain>` before running `make validate-production`.
3. The Telegram webhook must point to the live validation base URL used in step 1, ending with `/telegram/webhook`.
4. You must know the tester `telegram_user_id` or `telegram_chat_id`.
5. The tester's old rows should be cleared if you want a clean onboarding run.

Useful tools:

- inspect current state:
  - `.venv/bin/python scripts/inspect_telegram_user.py --telegram-user-id <id>`
- validate expected state:
  - `.venv/bin/python scripts/validate_telegram_user_state.py --telegram-user-id <id> ...`
- reset a tester to a clean slate:
  - dry-run: `.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id <id>`
  - execute: `.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id <id> --execute`

## 3. Candidate Onboarding Smoke

### Flow

1. Open the bot.
2. Send `/start`.
3. Share contact.
4. Confirm consent.
5. Choose `Candidate`.
6. Send a short text CV or experience summary.
7. Approve summary.
8. Send salary, location, and work format.
9. Send verification video.

### Expected product behavior

- bot explains each step in context
- candidate onboarding advances without manual admin intervention
- final candidate state becomes `READY`

### Validation commands

Check latest snapshot:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/inspect_telegram_user.py --telegram-user-id <id>
```

Assert final state:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_telegram_user_state.py \
  --telegram-user-id <id> \
  --require-user \
  --expect-candidate-state READY
```

Optional clean reset before rerunning:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id <id> --execute
```

## 4. Manager Onboarding Smoke

### Flow

1. Open the bot with a clean user.
2. Send `/start`.
3. Share contact.
4. Confirm consent.
5. Choose `Hiring Manager`.
6. Send a short text JD.
7. Answer clarification questions until vacancy opens.

### Expected product behavior

- manager onboarding advances through graph-owned intake
- vacancy transitions to `OPEN`

### Validation commands

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_telegram_user_state.py \
  --telegram-user-id <id> \
  --require-user \
  --expect-vacancy-state OPEN
```

## 5. Interview Invitation Smoke

### Flow

1. Ensure there is a candidate in `READY`.
2. Ensure there is a compatible `OPEN` vacancy.
3. Wait for matching + invitation or trigger the relevant background flow.
4. Candidate accepts the invitation.

### Expected product behavior

- invitation is delivered
- candidate can accept
- interview session is created

### Validation commands

Check invitation:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_telegram_user_state.py \
  --telegram-user-id <candidate-id> \
  --require-user \
  --expect-match-status invited
```

Check accepted/in-progress interview:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_telegram_user_state.py \
  --telegram-user-id <candidate-id> \
  --require-user \
  --expect-interview-state IN_PROGRESS
```

## 6. Manager Review Smoke

### Flow

1. Candidate completes interview.
2. Evaluation runs.
3. Manager receives review package.
4. Manager approves or rejects.

### Expected product behavior

- candidate package reaches manager
- manager decision is recorded

### Validation commands

Inspect latest review state:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/inspect_telegram_user.py --telegram-user-id <manager-id>
```

Useful fields to inspect:

- `latest_notification.template_key`
- `invited_match.status`
- `evaluation_result.status`

## 7. Delete Confirmation Smoke

### Candidate deletion

Flow:

1. Candidate in `READY` sends delete intent.
2. Bot asks for confirmation.
3. Candidate confirms or cancels.

Checks:

- candidate receives delete confirmation prompt
- after confirmation, active matches/interviews are canceled

### Manager deletion

Flow:

1. Manager with `OPEN` vacancy sends delete intent.
2. Bot asks for confirmation.
3. Manager confirms or cancels.

Checks:

- vacancy delete confirmation appears
- after confirmation, active matching/interview work is canceled

## 8. Failure Handling

If a smoke check fails:

1. Run:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/inspect_telegram_user.py --telegram-user-id <id>
```

2. Capture:

- current candidate/vacancy state
- latest notification template
- latest match status
- interview state
- evaluation status

3. Compare against the expected phase in this runbook.
4. Use the snapshot as the bug report payload.

## 9. Current Coverage Status

This runbook is the operational counterpart to:

- graph-native unit coverage
- graph-native integration coverage
- graph-owned Telegram routing coverage

What it adds is live-system verification against:

- Railway runtime
- Telegram webhook
- Supabase persistence
- real user messages
