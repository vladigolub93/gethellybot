.PHONY: run-api run-worker run-scheduler test db-upgrade db-current docker-build docker-test validate-production inspect-telegram-user validate-telegram-user-state validate-stage-help-safety reset-telegram-user report-telegram-user watch-telegram-user check-telegram-user-checkpoint

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

reset-telegram-user:
	.venv/bin/python scripts/reset_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID)

report-telegram-user:
	.venv/bin/python scripts/report_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID)

watch-telegram-user:
	.venv/bin/python scripts/watch_telegram_user.py --telegram-user-id $(TELEGRAM_USER_ID) --require-user

check-telegram-user-checkpoint:
	.venv/bin/python scripts/check_telegram_user_checkpoint.py --telegram-user-id $(TELEGRAM_USER_ID) --require-user

db-upgrade:
	alembic upgrade head

db-current:
	alembic current
