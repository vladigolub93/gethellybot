FROM python:3.12-slim

ARG INSTALL_DEV=0

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
COPY prompts /app/prompts
COPY tests /app/tests
COPY scripts /app/scripts

RUN pip install --upgrade pip && \
    if [ "$INSTALL_DEV" = "1" ]; then pip install ".[dev]"; else pip install .; fi

CMD ["bash", "scripts/start.sh"]
