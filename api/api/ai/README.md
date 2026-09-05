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

Agents today: `assistant_agent` (city Q&A), `triage_agent` (report triage) and
`category_agent` (open-text report → category classification; the focused agent
driven by the DeepEval loop under `eval/category_agent/`).

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

1. `cp -r versions/v1 versions/v2` (or subclass v1 — the `(from v1)` lineage; see
   `assistant_agent/versions/v2/agent.py`).
2. Edit `versions/v2/prompts.py` (and `agent.py` if behaviour changes). Make sure
   `versions/v2/__init__.py` exposes `AGENT`.
3. Score it against `datasets/` + `evaluations/`.
4. **Promote**: set `version: v2` in `versions/current.yaml`.

## Contract vs payload

`base.py` holds the `Abstract<Agent>` the domain depends on. The reference also
puts an agent's *result payload* models in `base.py`; here `triage_agent`'s result
(`TriageResult`) is a **domain** model owned by `city_events_bc`, so `base.py`
imports it rather than redefining it. `assistant_agent` returns a plain `str`.

## Build

The root `.dockerignore` drops `datasets/` and `evaluations/` (dev-only). The
version packages are code and all ship, so `current.yaml` can select any of them
at runtime.
