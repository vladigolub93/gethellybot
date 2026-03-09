.PHONY: run-api run-worker run-scheduler test db-upgrade db-current docker-build docker-test validate-production inspect-telegram-user validate-telegram-user-state validate-stage-help-safety validate-no-post-message-transition validate-graph-stage-logs validate-live-stage-checkpoint validate-live-scenario validate-phase-l report-phase-l-readiness reset-telegram-user report-telegram-user watch-telegram-user check-telegram-user-checkpoint export-telegram-conversation review-conversation-quality replay-telegram-update run-phase-l-synthetic

run-api:
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	python3 -m apps.worker.main

run-scheduler:
	python3 -m apps.scheduler.main

test:
	pytest

docker-build:
	docker build -t helly:local .

docker-test:
	docker build --build-arg INSTALL_DEV=1 -t helly:test .
	docker run --rm helly:test pytest -q

validate-production:
	bash scripts/validate-production.sh

inspect-telegram-user:
	.venv/bin/python scripts/inspect_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID)

validate-telegram-user-state:
	.venv/bin/python scripts/validate_telegram_user_state.py --telegram-user-id $(TELEGRAM_USER_ID)

validate-stage-help-safety:
	.venv/bin/python scripts/validate_stage_help_safety.py --telegram-user-id $(TELEGRAM_USER_ID)

validate-no-post-message-transition:
	.venv/bin/python scripts/validate_no_post_message_transition.py --telegram-user-id $(TELEGRAM_USER_ID)

validate-graph-stage-logs:
	.venv/bin/python scripts/validate_graph_stage_logs.py --expect-telegram-user-id $(TELEGRAM_USER_ID)

validate-live-stage-checkpoint:
	.venv/bin/python scripts/validate_live_stage_checkpoint.py --telegram-user-id $(TELEGRAM_USER_ID)

validate-live-scenario:
	.venv/bin/python scripts/validate_live_smoke_scenario.py --telegram-user-id $(TELEGRAM_USER_ID) --scenario $(LIVE_SCENARIO)

validate-phase-l:
	.venv/bin/python scripts/validate_phase_l.py --telegram-user-id $(TELEGRAM_USER_ID)

report-phase-l-readiness:
	.venv/bin/python scripts/report_phase_l_readiness.py

reset-telegram-user:
	.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID)

report-telegram-user:
	.venv/bin/python scripts/report_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID)

watch-telegram-user:
	.venv/bin/python scripts/watch_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID) --require-user

check-telegram-user-checkpoint:
	.venv/bin/python scripts/check_telegram_user_checkpoint.py --telegram-user-id $(TELEGRAM_USER_ID) --require-user

export-telegram-conversation:
	.venv/bin/python scripts/export_telegram_conversation.py --telegram-user-id $(TELEGRAM_USER_ID)

review-conversation-quality:
	.venv/bin/python scripts/review_conversation_quality.py --telegram-user-id $(TELEGRAM_USER_ID)

replay-telegram-update:
	.venv/bin/python scripts/replay_telegram_update.py --telegram-user-id $(TELEGRAM_USER_ID)

run-phase-l-synthetic:
	DB_USE_NULL_POOL=1 .venv/bin/python scripts/run_phase_l_synthetic.py --scenario $(SCENARIO)

db-upgrade:
	alembic upgrade head

db-current:
	alembic current
