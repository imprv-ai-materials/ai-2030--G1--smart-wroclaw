# Smart Wrocław

A citizen app for the city of **Wrocław** with two capabilities:

1. **Ask about the city** — an AI assistant answers maintenance questions
   (waste collection, water supply/outages, MPK public transport, road works,
   street lighting, parks & greenery).
2. **Report a problem** — citizens report issues they observe ("there's a water
   leak on X street"). Every report goes through a **human-in-the-loop (HITL)**
   review: an AI triages it, then a **city specialist approves or rejects** it
   before any response is published.

This is the first draft of one project inside the `imprv-materials` monorepo.

```
smart_wroclaw/            ← project root: Poetry (pyproject.toml, poetry.lock, .venv) lives here
├── api/      FastAPI · pypika · Inngest  (the backend service; package is api/api — see api/README.md)
├── ui/       Next.js · React · Tailwind v4 · shadcn/ui · TanStack Query  (see ui/README.md)
├── dev/      pypyr task pipelines that orchestrate the whole stack (api + ui + infra)
├── docs/     architecture notes
└── compose.yaml · Tiltfile · Dockerfile · migrations.Dockerfile   ← infra / runtime (at root)
```

## How it fits together

```
              ┌────────────────────────── UI (Next.js, :3002) ──────────────────────────┐
              │  /assistant   →  ask city-maintenance questions                          │
              │  /report      →  file an issue report + track its status                 │
              │  /specialist  →  HITL review queue (approve / reject AI triage)          │
              └───────────────────────────────┬─────────────────────────────────────────┘
                                               │  REST  /api/v1  (dev auth headers)
              ┌────────────────────────── API (FastAPI, :8101) ─────────────────────────┐
              │  assistant_bc     conversations · messages · runs                        │
              │  city_events_bc   issues · triage · report_reviews (HITL) · venues,      │
              │                   accidents (planned)                                    │
              └───────────────┬───────────────────────────────────────┬─────────────────┘
                        send  │ Inngest events                         │ Postgres (pypika)
              ┌───────────────▼─────────── Worker (:8103) ─────────────▼─────────────────┐
              │  assistant.run   → AI answers the question                               │
              │  report.triage   → AI classifies + drafts a response → PENDING_REVIEW    │
              └──────────────────────────────────────────────────────────────────────────┘
```

The architecture mirrors the sibling `imprv-ai-service` / `imprv-api` services:
bounded contexts, layered repositories/services, a pypika `DBClient`, an API/worker
split, and Inngest for background jobs.

## The human-in-the-loop, in one picture

```
citizen files report ─▶ AI triage (category · severity · department · draft reply)
                              │
                              ▼
                    specialist review queue ──▶  ✅ APPROVE → PUBLISHED (reply shown to citizen)
                    (edit any field first)  ──▶  ❌ REJECT  → REJECTED
```

Nothing the AI produces reaches a citizen until a human specialist signs off.

## Quick start

```bash
# from the project root (smart_wroclaw/): Postgres + Inngest + API + worker + UI, one command
cp api/.env.example api/.env && pypyr install && pypyr start_tilt

# or run the UI on its own
cd ui && pnpm install && pnpm dev     # http://localhost:3002
```

### Or: run it in a Dev Container (any OS)

Prefer a zero-setup, reproducible environment? Open the folder in VS Code and
**Reopen in Container** — Postgres, Inngest, Label Studio and the full Python +
Node toolchain come up as a Compose stack, identically on macOS / Windows / Linux.
No local Python/Node/Postgres needed. See [`.devcontainer/README.md`](.devcontainer/README.md).

See [`api/README.md`](api/README.md) and [`ui/README.md`](ui/README.md) for details.

## Status & next steps

First draft — end-to-end shape is in place; the AI agents have offline fallbacks
so everything runs without an OpenAI key. Known follow-ups:

- Real authentication (Auth0 / municipal SSO) — dev auth is header-based today.
- Ground the assistant in real municipal data (RAG over the city's open-data
  portal, GTFS, ticketing) instead of a static prompt briefing.
- Duplicate detection + routing to real city departments' ticketing systems.
