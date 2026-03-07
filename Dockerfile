FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini /app/
COPY apps /app/apps
COPY src /app/src
COPY migrations /app/migrations
COPY docs /app/docs
COPY scripts /app/scripts

RUN pip install --upgrade pip && pip install .

CMD ["bash", "scripts/start-api.sh"]

