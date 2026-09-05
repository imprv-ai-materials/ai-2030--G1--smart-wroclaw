# Runs `alembic upgrade head` against the configured Postgres. Kept as its own
# tiny image so schema changes deploy independently of the app (compose brings it
# up once, gated on the db healthcheck).
#
# Build context is the repo-module root (smart_wroclaw/) — compose.yaml and the
# Tiltfile set `context: .` so the api/ package is visible here.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.1.4 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-root

COPY api/alembic.ini ./api/alembic.ini
COPY api/api ./api/api

CMD ["alembic", "-c", "api/alembic.ini", "upgrade", "head"]
