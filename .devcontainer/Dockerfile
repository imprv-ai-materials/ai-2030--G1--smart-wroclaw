# Dev image for the Smart Wrocław devcontainer. It carries only the TOOLCHAIN
# (Python 3.12 · Poetry · Node 20 · pnpm · psql client) — no app code is baked
# in. The project source is bind-mounted and its dependencies are installed at
# create time by postCreate.sh, so the same image works on macOS, Windows (WSL2)
# and Linux hosts.
#
# Python + Poetry versions are kept in lock-step with the root Dockerfile so the
# container and the shipped image resolve the same environment.

FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

ENV POETRY_VERSION=2.1.4 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libs: build headers for psycopg2 (gcc + libpq) and the psql CLI for
# poking at the db from a terminal. curl/git/sudo already ship in the base image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential libpq-dev postgresql-client \
 && rm -rf /var/lib/apt/lists/*

# Node 20 (Next.js 16 requires >=20) via NodeSource, then pnpm through corepack.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && corepack enable \
 && corepack prepare pnpm@latest --activate

# Poetry in its own isolated venv (pinned), then put it on PATH for every user.
RUN python3 -m venv "${POETRY_HOME}" \
 && "${POETRY_HOME}/bin/pip" install --no-cache-dir "poetry==${POETRY_VERSION}"
ENV PATH="${POETRY_HOME}/bin:${PATH}"
