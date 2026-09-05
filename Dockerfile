# Smart Wrocław API / worker image. The same image runs both roles — the role
# is chosen at runtime via SMART_WROCLAW_ROLE (see api/api/main.py).
#
# Build from the repo-module root (smart_wroclaw/) so the api/ package is in the
# build context:
#
#   docker build -f Dockerfile -t smart-wroclaw .
#   docker run -e SMART_WROCLAW_ROLE=api    -p 8101:8101 smart-wroclaw uvicorn api.main:app --host 0.0.0.0 --port 8101
#   docker run -e SMART_WROCLAW_ROLE=worker -p 8103:8103 smart-wroclaw uvicorn api.main:app --host 0.0.0.0 --port 8103

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.4 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

# Install deps first (layer-cached) — only the app-code layer rebuilds on change.
# Poetry is rooted at the project root; the package stays at api/api so the
# pyproject `packages = [{ include = "api", from = "api" }]` resolves the same
# in the image as in dev.
COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-root

COPY api/api ./api/api
COPY api/alembic.ini ./api/alembic.ini
# pyproject `readme = "README.md"` → resolved at /app/README.md during the root install.
COPY README.md ./README.md
RUN poetry install --only main

ENV SMART_WROCLAW_ROLE=all
EXPOSE 8101
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8101"]
