# Smart Wrocław

A citizen app for the city of **Wrocław** with two capabilities:

1. **Ask about the city** — an AI assistant answers maintenance questions
   (waste collection, water supply/outages, MPK public transport, road works,
   street lighting, parks & greenery).
2. **Report a problem** — citizens report issues they observe. Every report goes
   through a **human-in-the-loop (HITL)** review: an AI triages it, then a **city
   specialist approves or rejects** it before any response reaches the citizen.

```
citizen files report ─▶ AI triage (category · severity · department · draft reply)
                              │
                              ▼
                    specialist review queue ──▶  ✅ APPROVE → PUBLISHED
                    (edit any field first)  ──▶  ❌ REJECT  → REJECTED
```

Nothing the AI produces reaches a citizen until a human specialist signs off.

## Run it (Dev Container — recommended)

A one-click, reproducible environment. Python 3.12, Poetry, Node 20, pnpm,
Postgres and the Inngest dev server all come up as a Compose stack — identically
on **macOS, Windows (WSL2) and Linux**. No local Python/Node/Postgres needed,
just Docker + an editor with Dev Containers support.

1. Open this folder in VS Code.
2. **Reopen in Container** (Command Palette → *Dev Containers: Reopen in
   Container*). First build takes a few minutes; `postCreate.sh` installs deps and
   applies migrations, then prints **"Devcontainer ready"**.
3. Start the app from two terminals:

   ```bash
   poetry run uvicorn api.main:app --app-dir api --host 0.0.0.0 --reload --port 8101   # REST + worker
   pnpm --dir ui dev                                                     # UI
   ```

Open the forwarded ports (VS Code → **Ports**):

| Service      | URL                        |
|--------------|----------------------------|
| UI           | http://localhost:3100      |
| API + docs   | http://localhost:8101/docs |
| Inngest      | http://localhost:8288      |

> Inside the container, use the plain `uvicorn` / `pnpm` commands above — **not**
> `pypyr start_tilt`, which hardcodes host-oriented URLs for the native workflow.

Full details, gotchas and the native (non-container) workflow:
[`.devcontainer/README.md`](.devcontainer/README.md).

## Layout

```
smart_wroclaw/            ← project root: Poetry (pyproject.toml, poetry.lock, .venv)
├── api/      FastAPI · pypika · Inngest — backend service (see api/README.md)
│   └── api/ai/<agent>/   each AI agent: versions/ · datasets/ · eval/ (its own scored loop)
├── ui/       Next.js · React · Tailwind v4 · shadcn/ui · TanStack Query (see ui/README.md)
├── dev/      pypyr task pipelines that orchestrate the stack (native workflow)
├── .annotator/  lightweight in-repo dataset annotator (see .annotator/README.md)
├── docs/     architecture notes + diagrams
└── compose.yaml · Tiltfile · Dockerfile   ← infra / runtime
```

The architecture mirrors the sibling `imprv-ai-service` / `imprv-api` services:
bounded contexts, layered repositories/services, a pypika `DBClient`, an API/worker
split, and Inngest for background jobs.

## Status & next steps

First draft — the end-to-end shape is in place, and the AI agents have offline
fallbacks so everything runs without an OpenAI key. Known follow-ups:

- Real authentication (Auth0 / municipal SSO) — dev auth is header-based today.
- Ground the assistant in real municipal data (RAG over the city's open-data
  portal, GTFS, ticketing) instead of a static prompt briefing.
- Duplicate detection + routing to real city departments' ticketing systems.
</content>
</invoke>
