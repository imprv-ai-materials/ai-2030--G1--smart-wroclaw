# `ai/` — agents: contract + versioned implementations + evals

One folder per agent, following the reference `imprv-ai-service` `agents_bc`
layout. Agent **code lives here** (moved out of each bounded context); the domain
services depend only on the `base.py` **contract**, so swapping a version never
touches the domain.

```
ai/<agent_name>/
├── base.py            Abstract<Agent> — the contract the domain service depends on
├── datasets/          eval inputs                              (dev-only)
├── evaluations/       eval definitions / expected outcomes     (dev-only)
└── versions/
    ├── v1/            agent.py (concrete impl) + prompts.py; __init__ exports AGENT
    ├── v2/            a later revision — often `(from v1)`, i.e. subclasses it
    └── current.yaml   names the ACTIVE version (+ optional model override)
```

Agents today — the **`main_agent`** composes the rest into one turn:
`guardrails_agent` (topic gate), `event_extractor` (text → `EventUnderstanding`),
`router_agent` (intent), `search_agent` (retrieval), `report_agent` (ingestion),
`analytics_agent` (counting) and the `geo_resolver` tool. Each has its own
`base.py` contract, `versions/`, `datasets/` and `evaluations/`.

## How a version is selected

`bootstrap.agents.get_<agent>()` calls `api.ai.load_current("<agent>")`, which
reads `versions/current.yaml`, imports `api.ai.<agent>.versions.<version>` and
uses its `AGENT` class. So **which version runs is a one-line YAML edit** — no
code change, no rebuild. All version packages ship in the image; promotion and
rollback are pure config.

```yaml
# versions/current.yaml
version: v1          # → imports api.ai.<agent>.versions.v1, uses its AGENT
model: null          # optional per-deployment model override
```

## Adding / promoting a version

1. `cp -r versions/v1 versions/v2` (or subclass v1 for a `(from v1)` lineage —
   keep the later version a thin diff over the earlier one).
2. Edit `versions/v2/prompts.py` (and `agent.py` if behaviour changes). Make sure
   `versions/v2/__init__.py` exposes `AGENT`.
3. Score it against `datasets/` + `evaluations/`.
4. **Promote**: set `version: v2` in `versions/current.yaml`.

## Contract vs payload

`base.py` holds the `Abstract<Agent>` the domain depends on, plus that agent's
*result payload* model when it has one (e.g. `guardrails_agent`'s `GuardrailVerdict`,
`report_agent`'s `ReportTurn`). Agents that return an existing domain type import it
rather than redefine it (e.g. `search_agent` returns `list[CityEvent]`).

## Build

The root `.dockerignore` drops `datasets/` and `evaluations/` (dev-only). The
version packages are code and all ship, so `current.yaml` can select any of them
at runtime.
