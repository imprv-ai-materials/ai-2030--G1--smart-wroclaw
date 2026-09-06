# Dev Container — run Smart Wrocław on any OS

A one-click, reproducible dev environment. Everything the stack needs — Python
3.12, Poetry, Node 20, pnpm, Postgres and the Inngest dev server — is provisioned
in containers, so it behaves the same on **macOS, Windows (WSL2) and Linux**. No
local Python/Node/Postgres install required; only Docker + an
editor with Dev Containers support (VS Code + the *Dev Containers* extension, or
the `devcontainer` CLI).

## Start it

1. Open the `smart_wroclaw/` folder in VS Code.
2. **Reopen in Container** (Command Palette → *Dev Containers: Reopen in
   Container*). First build takes a few minutes.
3. `postCreate.sh` runs automatically: it installs backend + frontend deps and
   applies the DB migrations. When it prints **"Devcontainer ready"**, start the
   app from two terminals:

   ```bash
   poetry run uvicorn api.main:app --app-dir api --host 0.0.0.0 --reload --port 8101   # REST + worker
   pnpm --dir ui dev                                                     # UI
   ```

Open the forwarded ports (VS Code → **Ports** panel):

| Service         | URL                          | Notes                                   |
|-----------------|------------------------------|-----------------------------------------|
| UI (Next.js)    | http://localhost:3100        |                                         |
| API + docs      | http://localhost:8101/docs   | REST + Inngest function host (role=all) |
| Inngest         | http://localhost:8288        | dev dashboard                           |
| Postgres        | localhost:5432 (forwarded)   | `smart_wroclaw` / `smart_wroclaw`       |

## "Can we fire up the compose from the devcontainer?" — yes, it *is* the compose

The devcontainer is defined **as a Compose stack** (`.devcontainer/compose.yaml`).
When you Reopen in Container, VS Code runs `docker compose up` on it for you, so
bringing the stack up is not a separate step — opening the container fires up the
compose. The services:

```
┌─ app ──────────────┐   the devcontainer you work in (source bind-mounted).
│  uvicorn :8101      │   run uvicorn (role=all → REST + worker) and pnpm here.
│  next  :3100        │
└─────────┬───────────┘
          │  db:5432          inngest:8288
   ┌──────▼─────┐      ┌──────────▼───────┐
   │ postgres:18│      │ inngest dev srv  │
   └────────────┘      │ -u app:8101/...  │
                       └──────────────────┘
```

Everything talks over the Compose network by **service name** (`db`, `inngest`),
so there's no `host.docker.internal` and no host-port juggling — that's what
makes it portable. Host access is via `forwardPorts`, so it never clashes with a
native `docker compose` / Tilt run.

### How this differs from the native (non-container) workflow

| | Native host (`compose.yaml` + Tilt) | Devcontainer (`.devcontainer/compose.yaml`) |
|---|---|---|
| Postgres / Inngest | containers, **published on localhost** | containers, **network-internal** |
| api / worker / ui | run **on your machine** (Poetry/pnpm) | run **inside the `app` container** |
| Orchestrator | **Tilt** (`pypyr start_tilt`) | Compose (auto, via the devcontainer) |
| DB address | `localhost:5439` (from `api/.env`) | `db:5432` (compose env override) |

> **Don't use `pypyr start_tilt` / `pypyr start_*` inside the container.** Those
> shortcuts hardcode host-oriented URLs (`127.0.0.1:8488`, Docker socket for
> Tilt) for the native workflow. In the container just run the plain `uvicorn` /
> `pnpm` commands above — DB host, Inngest URL and role are already set as
> container env vars.

## Annotating eval datasets

Dataset labelling uses the lightweight in-repo annotator at
[`/.annotator`](../.annotator/README.md) — no extra service. Point it at an
agent's dataset + template, e.g.:

```bash
python .annotator/annotate.py \
  api/api/ai/main_agent/datasets/annotate.template.js \
  api/api/ai/main_agent/datasets/queries.jsonl
# → http://127.0.0.1:7900
```

## Notes & gotchas

- **`.venv` and `ui/node_modules` are named volumes**, not the bind-mounted host
  folders — a macOS/Windows virtualenv or native module won't run under Linux, so
  the container keeps its own. If you ever change dependencies, re-run
  `poetry install` / `pnpm --dir ui install` (or rebuild the container).
- **git:** this container mounts only `smart_wroclaw/`, but the repo's `.git`
  lives at the monorepo root above it, so run `git` from the host (or open the
  monorepo root as the workspace if you prefer git inside the container).
- **OpenAI key:** left blank in the generated `api/.env`, so the assistant and
  triage agents use their offline fallbacks and the whole stack is exercisable
  with no key and no cost. Add `CONFIG__OPENAI__API_KEY=…` to `api/.env` to use a
  real model.
- **Rebuild** after changing anything under `.devcontainer/`: *Dev Containers:
  Rebuild Container*.
