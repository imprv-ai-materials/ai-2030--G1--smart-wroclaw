#!/usr/bin/env bash
# Runs once, inside the `app` container, after it's created. The db is already
# healthy at this point (app depends_on db: service_healthy), so migrations here
# are safe. Idempotent — re-running it is fine.
set -euo pipefail

cd "$(dirname "$0")/.."   # → smart_wroclaw project root

echo "▸ Taking ownership of the named-volume mount points (.venv, ui/node_modules)…"
# The volumes mount empty + root-owned; hand them to the current (vscode) user so
# poetry / pnpm can write into them.
sudo chown -R "$(id -u):$(id -g)" .venv ui/node_modules 2>/dev/null || true

# api/.env is gitignored, so a fresh clone won't have one. Seed dev defaults with
# NO OpenAI key (the agents fall back to offline heuristics). db host/port here
# match the compose network; they're also overridden by the container env vars.
if [ ! -f api/.env ]; then
  echo "▸ api/.env missing — writing dev defaults (offline, no secrets)…"
  cat > api/.env <<'ENV'
# Local dev config for the devcontainer. Gitignored.
CONFIG__POSTGRES__HOST=db
CONFIG__POSTGRES__PORT=5432
CONFIG__POSTGRES__DB=smart_wroclaw
CONFIG__POSTGRES__USER=smart_wroclaw
CONFIG__POSTGRES__PASSWORD=smart_wroclaw

# Leave the OpenAI key blank → assistant + triage agents use offline fallbacks.
CONFIG__OPENAI__API_KEY=
CONFIG__OPENAI__DEFAULT_MODEL_NAME=gpt-5.4

CONFIG__ASSISTANT__DEV_CITIZEN_ID=1
CONFIG__REPORTS__DEFAULT_DEPARTMENT=Centrum Zarządzania Kryzysowego
CONFIG__SPECIALIST__API_KEY=dev-specialist

CONFIG__APP__JWT_SECRET=dev-insecure-change-me-please-min-32-bytes-secret
CONFIG__APP__PASSWORD_PEPPER=dev-pepper
CONFIG__APP__UI_BASE_URL=http://localhost:3100

CONFIG__RESEND__API_KEY=
CONFIG__ENABLE_QUERY_LOGGING=false
ENV
fi

echo "▸ poetry install (backend deps + editable root → .venv)…"
# NOT --no-root: installing the root package writes the editable path entry that
# puts the inner api/ package on sys.path, so `uvicorn api.main:app` and alembic
# can `import api`. (the root Dockerfile does the same with its second install.)
poetry install

echo "▸ pnpm install (frontend deps → ui/node_modules)…"
pnpm --dir ui install

echo "▸ alembic upgrade head (apply the schema to the db service)…"
poetry run alembic -c api/alembic.ini upgrade head

cat <<'DONE'

✅ Devcontainer ready. Start the stack from separate terminals:

    poetry run uvicorn api.main:app --host 0.0.0.0 --reload --port 8101   # REST + Inngest worker (role=all)
    pnpm --dir ui dev                                                     # Next.js UI

Then open the forwarded ports (VS Code → Ports panel):
    UI            http://localhost:3100
    API docs      http://localhost:8101/docs
    Inngest       http://localhost:8288

DONE
