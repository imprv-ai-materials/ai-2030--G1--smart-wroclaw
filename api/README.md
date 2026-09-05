# Smart Wrocław — API

FastAPI backend for the Smart Wrocław citizen app. Three bounded contexts:

- **`auth_bc`** — resident accounts: email + password login (bcrypt + JWT),
  **email confirmation** and **password reset** via single-use hashed tokens sent
  through Resend (a console fallback logs the links in local dev), plus
  change-password. A citizen must confirm their email before filing an event.
  (The legacy `X-Citizen-Id` / `X-Specialist-Key` header identities are still
  accepted by the not-yet-migrated assistant / specialist surfaces.)
- **`assistant_bc`** — city-maintenance Q&A. A citizen opens a conversation and
  asks questions (waste, water, MPK, roads, lighting, greenery); each question is
  a background *run* that produces an AI answer.
- **`city_events_bc`** — things happening around the city. Two surfaces:
  - **`city_events`** — the geolocated citizen-map feed. Each event has a
    **type** (`ISSUE` / `ALARM` / `VENUE` / `PROMOTION`), a **status**
    (`ACTIVE` / `SCHEDULED` / `RESOLVED` / `EXPIRED`), a **source**
    (`CITY` / `CITIZEN` / `BUSINESS`) and optional `(lat, lng)`. Read side is
    public (map + "aktywne zdarzenia"); a logged-in, email-confirmed resident can
    file one.
  - **citizen issue reports** with a **human-in-the-loop (HITL)** review: a
    citizen files a report → an AI *triage agent* classifies it and drafts a
    response → a human **specialist** approves/rejects before publication.

## Architecture

This service is the `api/` folder, but Poetry is rooted at the project root
(`smart_wroclaw/`) — `pyproject.toml`, `poetry.lock` and `.venv` live there and
the package is `api/api` (`packages = [{ include = "api", from = "api" }]`).
Infra (Dockerfiles, compose, Tilt) lives at the project root (`..`); the
cross-cutting task pipelines live in `../dev`. The Python package itself:

```
api/                       ← the Python package (installed as `api`)
├── main.py                FastAPI app; role = api | worker | all (SMART_WROCLAW_ROLE)
├── bootstrap/             DI container (__init__) + agent factories (agents.py)
├── config.py              pydantic-settings, CONFIG__-prefixed env vars
├── inngest_app.py         shared Inngest client + event names
├── ai/                    agents: base.py contract · versions/ · datasets · evals (see ai/README.md)
│   ├── assistant_agent/   base.py + versions/{v1,v2}/(agent.py,prompts.py) + current.yaml
│   └── triage_agent/      base.py + versions/v1/(agent.py,prompts.py) + current.yaml
├── adapters/
│   ├── db/                pypika-over-psycopg DBClient + Alembic migrations
│   ├── llm/               thin OpenAI wrapper (offline-safe)
│   └── websockets.py      in-process push manager (/ws/{topic}); polling is the fallback
├── shared/                exceptions (cross-cutting base errors)
└── contexts_boundaries/
    ├── auth_bc/           citizen / specialist identities + FastAPI deps
    ├── assistant_bc/      models · repositories(+tables) · services · rest · inngest
    └── city_events_bc/    models · repositories(+tables) · services · rest · inngest
```

The agents live in `ai/` (contract in `base.py`, concrete versions under
`versions/`); each bounded context is layered: **models** (Pydantic + `from_dict`)
→ **repositories** (pypika tables + `DBClient`) → **services** (orchestration +
domain rules, depending on an agent's `ai/…/base.py` contract) → **rest**
(FastAPI routers) → **inngest_functions** (worker jobs). The **LLM agent** each
service calls is wired in from `ai/` by the composition root.

### API / worker split

The same app image runs in one of three roles (env `SMART_WROCLAW_ROLE`):

| role   | serves                          | port (dev) |
|--------|---------------------------------|------------|
| `api`  | REST routers                    | 8101       |
| `worker`| `/api/inngest` (function host) | 8103       |
| `all`  | both (single-process dev)       | —          |

REST endpoints only persist + `inngest_client.send(...)`; the heavy AI work runs
on the worker, so a burst of triage/answer jobs can't starve interactive traffic.

## The HITL loop (city_events_bc)

```
citizen        POST /reports                 → SUBMITTED  ──fires──▶ smart_wroclaw/report.triage
worker         run_triage()                  → TRIAGING → PENDING_REVIEW  (AI proposal attached)
specialist     POST /specialist/reports/{id}/review
                 APPROVE → PUBLISHED   (specialist edits win over the AI proposal;
                                        public_response becomes visible to the citizen)
                 REJECT  → REJECTED
```

`run_triage` is the **only** automated status change — publication *always* requires
a human `review()`. The specialist can override every field (category, severity,
routing department, the public response) the AI proposed. Every decision is recorded
in `report_reviews` (audit trail) transactionally with the report state change.

> The AI agents degrade gracefully: with no `CONFIG__OPENAI__API_KEY` set, the
> assistant returns a templated answer and the triage agent uses a keyword
> heuristic — so the whole stack (and the HITL queue) is fully exercisable offline.

## Running locally

Prereqs: Python 3.12, Poetry, Docker, and [Tilt](https://tilt.dev) (optional).

All commands run from the **project root** (`smart_wroclaw/`, where
`pyproject.toml` and `.venv` now live). The pypyr shortcuts wrap the pipelines in
`dev/`; infra lives at the project root; this package's env file stays at `api/.env`.

```bash
cp api/.env.example api/.env
pypyr install            # poetry install + pre-commit + pnpm install in ui/

# one command: Postgres + Inngest dev server + migrations + api + worker + ui
pypyr start_tilt         # → tilt up -f Tiltfile
```

…or by hand, without Tilt:

```bash
docker compose --env-file api/.env up -d db inngest   # Postgres :5439, Inngest UI :8488
poetry run alembic -c api/alembic.ini upgrade head     # apply the schema
SMART_WROCLAW_ROLE=api    poetry run uvicorn api.main:app --reload --port 8101
SMART_WROCLAW_ROLE=worker poetry run uvicorn api.main:app --reload --port 8103
```

- REST + OpenAPI docs: <http://localhost:8101/docs>
- Inngest dev dashboard: <http://localhost:8488>

## Seeding demo events

`api/datasets/fake_events.json` holds ~24 realistic Wrocław events across all
four types. Load them so the citizen map has something to render:

```bash
poetry run python api/scripts/seed_events.py            # default dataset
# or via HTTP (dev convenience; needs X-Specialist-Key):
curl -X POST localhost:8101/api/v1/events/ingest \
  -H 'X-Specialist-Key: dev-specialist' -H 'content-type: application/json' \
  --data @api/datasets/fake_events.json    # wrap the array in {"events": [...]} for HTTP
```

## Key endpoints (prefix `/api/v1`)

**Auth** — `POST /auth/register`, `POST /auth/login`, `GET /auth/me` (Bearer),
`POST /auth/confirm-email`, `POST /auth/resend-confirmation`,
`POST /auth/request-password-reset`, `POST /auth/reset-password`,
`POST /auth/change-password` (Bearer).

**Events (citizen map)** — `GET /events?status=&type=`, `GET /events/{id}`
(both public), `POST /events` (Bearer + confirmed email),
`POST /events/ingest` (`X-Specialist-Key`, bulk seed).

**Assistant** — `GET/POST /conversations`, `GET/DELETE /conversations/{id}`,
`GET /conversations/{id}/messages`, `POST /conversations/{id}/runs`,
`GET /conversations/{id}/runs/active`, `.../runs/{run_id}/events?since=`.

**Reports (citizen)** — `POST /reports`, `GET /reports`, `GET /reports/{id}`.

**Reports (specialist, needs `X-Specialist-Key`)** —
`GET /specialist/reports?status=PENDING_REVIEW`, `GET /specialist/reports/{id}`,
`POST /specialist/reports/{id}/review`.

## Auth

- **Resident login** (`auth_bc`) — email + password → JWT
  (`Authorization: Bearer <jwt>`). Registration sends a confirmation email;
  password reset / change and email confirmation use single-use hashed tokens.
  Configure `CONFIG__APP__JWT_SECRET`, `CONFIG__APP__PASSWORD_PEPPER`,
  `CONFIG__APP__UI_BASE_URL`, and `CONFIG__RESEND__API_KEY` (optional — without
  it, links are logged to the console). See `api/.env`.
- **Legacy placeholders** (kept for assistant / specialist until migrated):
  `X-Citizen-Id` header, and the specialist shared secret `X-Specialist-Key`.
