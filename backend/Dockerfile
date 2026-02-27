FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/base.txt

FROM base AS dev

COPY requirements/dev.txt requirements/dev.txt
RUN pip install --no-cache-dir -r requirements/dev.txt

COPY . .
RUN chmod +x entrypoint.sh

# ──── Lint / type-check (used in CI and `docker compose run lint`) ────
FROM dev AS lint

RUN ruff check . \
    && ruff format --check . \
    && mypy --config-file=/app/pyproject.toml .

FROM base AS prod

COPY requirements/prod.txt requirements/prod.txt
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .
RUN chmod +x entrypoint.sh

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser
