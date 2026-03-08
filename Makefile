.PHONY: run-api run-worker run-scheduler test db-upgrade db-current docker-build docker-test validate-production

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

db-upgrade:
	alembic upgrade head

db-current:
	alembic current
