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

# Claude Code CLI — global npm install on the Node 20 toolchain above. Baked into
# the image so `claude` is on PATH the moment the container starts (no per-create
# download).
RUN npm install -g @anthropic-ai/claude-code

# `penv` shortcut → activate the in-project virtualenv from anywhere in the tree.
# The .venv is a named volume populated by postCreate.sh's `poetry install`, so
# the dev deps (pytest, black, mypy, …) resolve once you've run `penv`.
RUN echo "alias penv='source /workspaces/smart_wroclaw/.venv/bin/activate'" >> /home/vscode/.bashrc

# Entrypoint that aligns the `vscode` uid/gid with the bind-mounted workspace
# owner on Linux hosts (compose devcontainers don't get VS Code's automatic
# updateRemoteUserUID). Wired up as `entrypoint:` in compose.yaml.
COPY entrypoint.sh /usr/local/bin/devcontainer-entrypoint.sh
RUN chmod +x /usr/local/bin/devcontainer-entrypoint.sh

# Poetry in its own isolated venv (pinned), then put it on PATH for every user.
RUN python3 -m venv "${POETRY_HOME}" \
 && "${POETRY_HOME}/bin/pip" install --no-cache-dir "poetry==${POETRY_VERSION}"
ENV PATH="${POETRY_HOME}/bin:${PATH}"
