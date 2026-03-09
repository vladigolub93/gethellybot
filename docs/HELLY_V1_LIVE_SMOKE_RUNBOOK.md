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
6. If Supabase session-pooler starts rejecting local validation scripts with `MaxClientsInSessionMode`, run those scripts with `DB_USE_NULL_POOL=1`.
7. Before attempting automated Phase L checks, run:
   - `.venv/bin/python scripts/report_phase_l_readiness.py`
7. Treat Phase L readiness in two modes:
   - `can_validate_after_real_user_input`: live DB/log validation can run after you manually send the Telegram message
   - `can_drive_synthetic_webhook_posts`: this machine can also replay synthetic webhook traffic without manual Telegram input

Useful tools:

- inspect current state:
  - `.venv/bin/python scripts/inspect_telegram_user.py --telegram-user-id <id>`
- print a compact smoke report:
  - `.venv/bin/python scripts/report_telegram_user.py --telegram-user-id <id>`
- export recent conversation turns:
  - `.venv/bin/python scripts/export_telegram_conversation.py --telegram-user-id <id> --include-pending-notifications --format markdown`
- review likely robotic Helly turns:
  - `.venv/bin/python scripts/review_conversation_quality.py --telegram-user-id <id> --include-pending-notifications`
- watch until a live condition is reached:
  - `.venv/bin/python scripts/watch_telegram_user.py --telegram-user-id <id> --require-user --expect-candidate-state SUMMARY_REVIEW`
- wait and print a final checkpoint report in one command:
  - `.venv/bin/python scripts/check_telegram_user_checkpoint.py --telegram-user-id <id> --require-user --expect-candidate-state READY`
- validate expected state:
  - `.venv/bin/python scripts/validate_telegram_user_state.py --telegram-user-id <id> ...`
- validate that a help question did not trigger an incorrect transition:
  - `.venv/bin/python scripts/validate_stage_help_safety.py --telegram-user-id <id> ...`
- validate that the latest inbound message did not produce a newer state transition:
  - `.venv/bin/python scripts/validate_no_post_message_transition.py --telegram-user-id <id> ...`
- validate that Railway logs contain the graph-owned stage execution event:
  - `.venv/bin/python scripts/validate_graph_stage_logs.py --expect-telegram-user-id <id> --expect-stage <stage>`
- run one composite validation for a live checkpoint:
  - `.venv/bin/python scripts/validate_live_stage_checkpoint.py --telegram-user-id <id> ...`
- run one predefined Phase L scenario validation:
  - `.venv/bin/python scripts/validate_live_smoke_scenario.py --telegram-user-id <id> --scenario <scenario>`
- run all remaining Phase L validations together:
  - `.venv/bin/python scripts/validate_phase_l.py --telegram-user-id <id>`
- print readiness/blockers for automated Phase L validation:
  - `.venv/bin/python scripts/report_phase_l_readiness.py`
  - this now reports both global blockers and per-scenario readiness for the remaining Phase L checks
- reset a tester to a clean slate:
  - dry-run: `.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id <id>`
  - execute: `.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id <id> --execute`
- force local validation tooling to avoid holding pooled DB connections:
  - `DB_USE_NULL_POOL=1 .venv/bin/python scripts/reset_telegram_user.py --telegram-user-id <id> --execute`
- replay a synthetic Telegram update directly through the live runtime without the webhook endpoint:
  - `.venv/bin/python scripts/replay_telegram_update.py --telegram-user-id <id> --text "/start" --username <telegram_username>`
  - useful when `TELEGRAM_WEBHOOK_SECRET` is not available locally but you still need to exercise the same stage-agent/runtime path against live Supabase data
- run the remaining Phase L scenarios synthetically through the live runtime:
  - `DB_USE_NULL_POOL=1 .venv/bin/python scripts/run_phase_l_synthetic.py --scenario all`
  - useful when manual Telegram proof is not available yet but you still need a reproducible runtime-level check for the most failure-prone stage-agent scenarios

Conversation review artifact:

- write down the strongest wording/UX issues in:
  - `docs/HELLY_V1_CONVERSATION_REVIEW_FINDINGS.md`

Railway log check:

- after each live smoke step, confirm the API logs contain `graph_stage_executed`
- useful fields in that log line:
  - `stage`
  - `stage_status`
  - `proposed_action`
  - `action_accepted`
  - `telegram_user_id`

Example:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_graph_stage_logs.py \
  --expect-telegram-user-id <id> \
  --expect-stage SUMMARY_REVIEW
```

## 3. Candidate Onboarding Smoke

### Flow

1. Open the bot.
2. Send `/start`.
3. If you do not have a Telegram username, share contact.
4. Choose `Candidate`.
5. Send a short text CV or experience summary.
6. Approve summary.
7. Send salary, location, and work format.
8. Send verification video.

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
3. If you do not have a Telegram username, share contact.
4. Choose `Hiring Manager`.
5. Send a short text JD.
6. Review the generated vacancy summary, correct it once if needed, then approve it.
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

## 6.1 Help-Question Safety Checks

Candidate summary review:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_stage_help_safety.py \
  --telegram-user-id <candidate-id> \
  --expect-candidate-state SUMMARY_REVIEW \
  --expect-latest-inbound-contains "How long" \
  --forbid-candidate-version-source-type summary_user_edit
```

Optional stricter check:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_no_post_message_transition.py \
  --telegram-user-id <candidate-id> \
  --expect-inbound-contains "How long"
```

## 6.2 Conversation Quality Review

After a live smoke run, export the recent chat and review the top robotic Helly turns:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/export_telegram_conversation.py \
  --telegram-user-id <id> \
  --format markdown \
  --limit 60
```

```bash
set -a
source .env
set +a
.venv/bin/python scripts/review_conversation_quality.py \
  --telegram-user-id <id> \
  --limit 80 \
  --top 10
```

Use that output to:

1. collect candidate onboarding snippets
2. collect manager onboarding snippets
3. identify the top robotic turns
4. map each turn to either prompt tuning or runtime microcopy cleanup

Manager vacancy summary review:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_stage_help_safety.py \
  --telegram-user-id <manager-id> \
  --expect-vacancy-state VACANCY_SUMMARY_REVIEW \
  --expect-latest-inbound-contains "How long" \
  --forbid-vacancy-version-source-type summary_user_edit
```

Railway log verification for the same step:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_graph_stage_logs.py \
  --expect-telegram-user-id <manager-id> \
  --expect-stage VACANCY_SUMMARY_REVIEW
```

Composite validation for the same step:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_live_stage_checkpoint.py \
  --telegram-user-id <manager-id> \
  --expect-vacancy-state VACANCY_SUMMARY_REVIEW \
  --expect-inbound-contains "How long" \
  --forbid-vacancy-version-source-type summary_user_edit \
  --expect-log-stage VACANCY_SUMMARY_REVIEW \
  --railway-token "$RAILWAY_API_TOKEN" \
  --railway-environment-id "$RAILWAY_ENVIRONMENT_ID"
```

Predefined scenario wrappers:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_live_smoke_scenario.py \
  --telegram-user-id <candidate-id> \
  --scenario candidate_summary_review_help
```

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_live_smoke_scenario.py \
  --telegram-user-id <candidate-id> \
  --scenario candidate_questions_clarification
```

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_live_smoke_scenario.py \
  --telegram-user-id <manager-id> \
  --scenario manager_vacancy_summary_review_help
```

Run all three remaining Phase L scenarios:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/validate_phase_l.py \
  --telegram-user-id <id>
```

Interpretation:

- if `report_phase_l_readiness.py` says `can_validate_after_real_user_input=true`, you can complete Phase L by interacting with the live bot and then running the validators locally
- if it also says `can_drive_synthetic_webhook_posts=true`, this machine can drive synthetic webhook replay in addition to post-message validation
- if both are `false`, fix the reported blockers before expecting automated Phase L completion

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
