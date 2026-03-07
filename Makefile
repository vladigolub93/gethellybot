.PHONY: run-api run-worker run-scheduler test

run-api:
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	python3 -m apps.worker.main

run-scheduler:
	python3 -m apps.scheduler.main

test:
	pytest

