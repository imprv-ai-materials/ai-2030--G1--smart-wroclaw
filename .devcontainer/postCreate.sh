#!/usr/bin/env bash
# Runs once, inside the `app` container, after it's created. The db is already
# healthy at this point (app depends_on db: service_healthy), so migrations here
# are safe. Idempotent — re-running it is fine.
set -euo pipefail

cd "$(dirname "$0")/.."   # → smart_wroclaw project root

# The workspace is a bind mount. If the container user can't write to it, nothing
# below can work (and the editor can't save files either). Normally entrypoint.sh
# has already remapped `vscode` to the host uid; this is the loud fallback.
if [ ! -w . ]; then
  cat >&2 <<MSG
✗ $(pwd) is not writable by $(id -un) (uid $(id -u)); it is owned by uid $(stat -c %u .).
  The container user must match the owner of the bind-mounted source tree.
  • Linux host: the entrypoint should have remapped the user — rebuild the
    container (Dev Containers: Rebuild Container) so the new image is used.
  • Rootless Docker / Podman: set "remoteUser": "root" in devcontainer.json,
    or run podman with --userns=keep-id.
MSG
  exit 1
fi

echo "▸ Taking ownership of the named-volume mount points (.venv, ui/node_modules, ui/.next)…"
# The volumes mount empty + root-owned; hand them to the current (vscode) user so
# poetry / pnpm / next can write into them. ui/.next MUST be here too — it's a
# named volume (see compose.yaml) that shadows the bind mount, so next dev can't
# mkdir .next/dev under it until vscode owns it ("EACCES: mkdir …/ui/.next/dev").
# Not silenced on purpose: if this fails, everything after it fails less clearly.
sudo chown -R "$(id -u):$(id -g)" .venv ui/node_modules ui/.next

# Seed the virtualenv ourselves when it's missing or broken (fresh/stale volume).
# Poetry would otherwise try to rmtree(.venv) to "recreate" it; .venv is a mount
# point, so that only works when the failure is EBUSY — with any other error
# (e.g. EACCES on the parent dir) poetry aborts. `venv --clear` empties the dir
# in place without ever removing the mount point, so poetry just adopts it.
if [ ! -x .venv/bin/python ]; then
  echo "▸ .venv is empty or broken — seeding it with python3 -m venv…"
  python3 -m venv --clear .venv
fi

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

    pypyr start_be      # REST + Inngest worker in ONE role=all process on :8101
    pypyr start_ui      # Next.js UI

⚠️  In the devcontainer use `pypyr start_be` — NOT `start_api` / `start_worker`.
    Those target the native host stack: they set INNGEST_DEV=127.0.0.1:8488 (dead
    inside the container) and split into two processes the container's Inngest dev
    server (pointed at app:8101) won't discover — chat turns then fail with
    "Coś poszło nie tak" (inngest send: "never received response").

    Equivalent raw command if you prefer (inherits INNGEST_DEV=inngest:8288):
    poetry run uvicorn api.main:app --host 0.0.0.0 --reload --port 8101

Then open the forwarded ports (VS Code → Ports panel):
    UI            http://localhost:3100
    API docs      http://localhost:8101/docs
    Inngest       http://localhost:8288

DONE
