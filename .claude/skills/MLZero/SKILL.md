---
name: MLZero
description: Metric-driven, dataset-first loop for improving any api/api/ai agent — driven by defects AND by optimization/experiments (a cheaper or faster model, a new prompt technique, a different approach). Use after a bad chat turn or bug, to proactively raise scores, or whenever you want to build a candidate version (e.g. on a cheaper model) and A/B it against the datasets. MLZero measures on the dataset with the evals, forms a hypothesis, changes the agent, and re-measures — keeping a change only if it meets its goal (bug fixed, or quality held within an agreed tolerance at lower cost) with no regression. A bug fix must first capture the failing case in the dataset; it ALWAYS asks whether to edit the current version in place or fork a new version first.
---

# MLZero — measure → change → re-measure, until it's better (or provably not)

MLZero improves an agent the way a training loop improves a model: **the metric is
the boss.** You never "just change the code." Every change is a hypothesis that must be
proven against a dataset you can re-run. A change is driven either by a **defect** (a
wrong or weak answer to fix) or by an **experiment / optimization** — a cheaper or
faster model, a new prompt technique, a leaner projection, a different approach. Either
way the dataset is the judge: keep the change only if it meets its stated goal with no
regression, otherwise revert. That's the whole discipline.

The loop at a glance: `docs/mlzero.svg` (source `docs/mlzero.mmd` —
`mmdc -i docs/mlzero.mmd -o docs/mlzero.svg`).

The two iron rules that make it work:

1. **The dataset is the judge — measure before and after, always.** For a **defect**,
   capture the failing case as a gold row *first*, so the fix is measurable and can't
   silently regress. For an **experiment**, the existing dataset is already the
   benchmark — add cases only if you're probing a specific gap. Never ship a change you
   haven't scored on the dataset.
2. **Ask before you modify.** Agent changes are either edited **in place** (current
   version) or forked into a **new version** (a copy). This is the user's call — stop
   and ask which, every time (see [The version gate](#the-version-gate)).

## What we have to work with

Everything lives under `api/api/ai/<agent>/`. The agents are `guardrails_agent`,
`event_extractor`, `router_agent`, `search_agent`, `report_agent`, `analytics_agent`,
`geo_resolver`, and the composed `main_agent`. Each folder is self-contained:

```
api/api/ai/<agent>/
├── base.py              the contract the domain depends on (don't break it)
├── datasets/            *.jsonl gold cases  ← what we measure against
│   ├── <name>.jsonl       one row per case: input + expected output + split + difficulty
│   ├── corpus.jsonl       (search_agent only) the events the ranker searches over
│   └── annotate.template.js
├── evaluations/*.yaml   the metric spec: which fields to assert, how to score
└── versions/
    ├── v1/{agent.py, prompts.py, __init__.py}   the actual agent code we change
    ├── v2/ …            later revisions (often a thin diff over v1)
    └── current.yaml     names the ACTIVE version — a one-line promote/rollback
```

- **Datasets** are the ground truth. A row is the input exactly as a resident typed it
  plus the **correct expected output** (the label — what SHOULD happen, not what the
  agent did), with `split: dev|test`, `difficulty: easy|medium|hard`, and a `note`.
- **Evals** (`evaluations/*.yaml`) define the metric: `field_equals` / `set_equals`
  assertions roll up to **accuracy** (+ per-assertion rates); a `ranking` assertion
  switches the whole eval to IR metrics (**Hit@1 / MRR / Recall@k**, plus must-exclude
  leaks) for `search_agent`.
- **Samples** are how you go fast. `sample=<pct>` runs a deterministic, evenly-spaced
  slice of the split (not the first N) — use a small sample to iterate quickly, then a
  full run to decide. Offline (each agent's keyword baseline) is the default and the
  floor you must beat; `llm=1` is the ceiling.

### The boundary rule: an agent reads bounded-context data through the SERVICE

Some agents need data owned by a bounded context — `search_agent`, `analytics_agent`
and `report_agent` all read `city_events`. They do so **only through that BC's
service** (`EventsService`), **never its repository or raw SQL**. The service is the
boundary: it owns the domain read rules (the expiry drop, the free-text `q` pass, the
`types` candidate-set facet), so an agent calls `events_service.list_events(...)` and
never re-implements those rules. The composition roots enforce this — production
(`api/api/bootstrap/agents.py`) and the eval harness (`api/api/ai/_eval/harness.py`)
both inject the **service**, the eval wrapping even its corpus-backed in-memory repo
in a real `EventsService` so the offline score exercises the true production read path.

The same rule governs every cross-context call: when one BC (or the chat orchestrator)
touches another's data it goes through that BC's service — `chat_bc`'s durable turn
creates events via `events_service.create_event(...)`, not the repository. So when a
change here needs bounded-context data:

- **Inject the service, not the repository.** A new (or forked) agent that reads a BC
  takes `Abstract<X>Service` in its constructor. Update BOTH composition roots
  (`bootstrap/agents.py` and `_eval/harness.py`) to pass the service.
- **Missing a read? Extend the service, don't reach past it.** If `list_events` (or
  the relevant service method) doesn't expose the filter/shape you need, add it to the
  **service** — that keeps each domain rule (expiry, etc.) in exactly one home instead
  of duplicated inside an agent.

## Measuring — the only source of truth

```bash
pypyr eval                                        # list agents + their datasets/specs
pypyr eval agent=<agent>                           # score CURRENT version, dev split, 100%
pypyr eval agent=<agent> sample=25                 # fast pass on a 25% slice while iterating
pypyr eval agent=<agent> split=all                 # full run before you decide to keep a change
pypyr eval agent=<agent> version=v2                # score a specific version (compare v1 vs v2)
pypyr eval agent=<agent> show_errors=1             # list the per-row failures to read
pypyr eval agent=<agent> llm=1                     # use the real LLM path (the ceiling)
pypyr eval agent=<agent> history=1                 # show past runs; don't re-run
```

Every real run is appended to `api/api/ai/<agent>/eval_runs.jsonl` automatically
(pass `no_store=1` to skip). That ledger is how you compare "before vs after" — read it
with `history=1`. **Never edit the eval scorer or the gold labels to make a number go
up.** If the metric is wrong, that's a separate, explicit conversation; the default is
to fix the agent, not the ruler.

## Two drivers: a defect, or an experiment

The same measure→change→re-measure loop serves both, but they start differently and are
judged differently.

- **Defect-driven** — a wrong/weak answer (a bad chat turn, a bug report, your own
  testing). Goal: *fix this and don't regress.* It is **mandatory** to capture the
  failing case in the dataset and baseline it RED first (loop steps 1–3), so the fix is
  provable.

- **Experiment / optimization-driven** — you or the user want to *try something*: a
  **cheaper or faster model**, a new prompt technique, a leaner projection, a different
  approach. There may be no failing case — the **existing datasets are the benchmark**,
  and their job is to prove the change doesn't quietly cost quality. Before building
  anything, **agree the objective and tolerance** with the user, e.g. *"switch to the
  cheaper model as long as accuracy drops ≤ 1 pt"* — that tolerance is the keep/revert
  threshold. Experiments are almost always **forked** (you want the candidate vs the
  baseline head-to-head, and one-line rollback).

### Swapping the model (the common experiment)

A model swap only shows up in the metrics on the **`llm=1`** path — the offline baseline
is a deterministic keyword heuristic and is model-independent, so a cheaper model changes
nothing offline. To A/B a model faithfully:

1. **Fork** a version (the version gate below) and **pin the cheaper model in it** — each
   version's `agent.py` takes a `model=` (see `guardrails_agent/versions/v1/agent.py`),
   so set the candidate model as that version's default. Pinning it *in the version* is
   what the eval scores (the harness builds each version with its own default);
   `current.yaml`'s `model:` is the **production** override the service wiring applies on
   promotion.
2. **Score candidate vs baseline on the LLM path**, full split:
   `pypyr eval agent=<agent> version=<candidate> llm=1 split=all` vs
   `pypyr eval agent=<agent> version=<baseline> llm=1 split=all`, then compare with
   `history=1`.
3. **Keep on the trade-off**: promote (`version: <candidate>` + its `model:` in
   `current.yaml`) only if quality stays within the agreed tolerance while the
   cost/latency objective is met. A cheaper model that drops quality past tolerance is a
   *reject*, reported with the numbers — not a ship.

## The MLZero loop

For a **defect**, start at step 1. For an **experiment**, you've already set the
objective + tolerance and the dataset is your benchmark — **start at step 4** (the
version gate); only drop back to step 2 if you're adding cases to probe a specific gap.

1. **Locate the failing turn(s).** From a chat, read `chat_conversations` /
   `chat_messages` in Postgres (each assistant row's `data.intent` names the lane that
   ran; `?chat=<id>` in the UI is the `conversation_id`). Identify **which agent**
   produced the bad output — trace guardrails → extractor → router → lane. A wrong
   answer often originates *upstream* of where it surfaces.

2. **Capture it in the dataset (this comes before any code).** Add the case to
   `api/api/ai/<agent>/datasets/<name>.jsonl`: the exact input + the correct expected
   output, `difficulty: hard` for traps, and a `note` citing the source (e.g. `"chat 3"`).
   Annotator: `pypyr annotate agent=<agent> dataset=<name>`. If the failure spanned
   agents, add the case at **each** layer it touched (the extractor's dataset AND the
   downstream agent's), not only the last one.

3. **Baseline it (expect red).** `pypyr eval agent=<agent> show_errors=1` — the new
   case should FAIL, proving it captures the bug and giving you the number to beat.

4. **Decide where the change goes — ASK (see [The version gate](#the-version-gate)).**
   Do not edit any agent file until the user has chosen in-place vs. new version.

5. **Apply ONE change.** One hypothesis at a time — a prompt (`versions/vN/prompts.py`),
   a heuristic / projection, or deterministic code (`versions/vN/agent.py`). For an
   experiment this is the model pin, the new prompt technique, or the alternative
   approach — still exactly one change, or you can't attribute the result.

6. **Re-measure.** Fast slice first (`sample=25`) to see if the hypothesis has legs,
   then the full picture:
   - the captured case now **passes** (defect), or quality lands **within tolerance**
     (experiment), and
   - `pypyr eval agent=<agent> split=all` shows **no regression** vs. the ledger
     (`history=1`), and if you forked, the candidate meets its bar vs the baseline
     (`version=<candidate>` vs `version=<baseline>`).
   - For a **model swap**, measure on `llm=1` — the offline baseline is model-independent.

7. **Keep or revert — the goal decides.**
   - **Goal met, nothing regressed** → keep it; if it's a new version, promote by setting
     `version: vNEW` (+ its `model:` for a swap) in `versions/current.yaml`. "Goal met"
     is *the case now passes* for a defect, or *quality within the agreed tolerance while
     the cost/latency/technique objective is achieved* for an experiment.
   - **Goal missed or a regression elsewhere** → revert and form a new hypothesis. Don't
     keep a change that failed its bar — a cheaper model that drops accuracy past
     tolerance is a *reject*, not a *ship*.

8. **Iterate until the goal is met — or accept it isn't.** Loop steps 5–7. Stop when the
   goal is satisfied, or successive hypotheses stop moving it (diminishing returns / the
   offline baseline can't express the change — a follow-up may need `llm=1` or a dataset
   richer in that case). "We tried and it didn't beat the bar" is a valid, honest outcome
   — report it with the numbers rather than forcing a change through.

## The version gate

**Before editing any file under `versions/`, stop and ask the user which path to take.**
Never assume. Present the two options and their trade-offs:

- **Edit in place** (change `versions/<current>/` directly) — simplest; right for a low-risk
  fix, a bug in the current version, or when you don't need to keep the old behavior around
  to compare. You lose the easy side-by-side; the eval ledger is your before/after.
- **Fork a new version** (`cp -r versions/vN versions/vN+1`, edit the copy, then flip
  `versions/current.yaml` to promote) — right for prompt/behavior changes, anything risky,
  or when you want to score old vs new head-to-head (`pypyr eval agent=<agent> version=vN`
  vs `version=vN+1`) and keep rollback to a one-line YAML edit. Keep the new version a thin
  diff over the old (subclass for a `(from vN)` lineage).

Use `AskUserQuestion` for this decision. Recommend the fork for prompt/behavior work and
**for every experiment/optimization** (model swaps, new techniques — you want the A/B and
the rollback), and in-place for small deterministic bug fixes; but let the user choose.
Only after they answer do you touch `versions/`.

## Rules

- **The dataset is the judge.** Score every change on it before and after; a defect fix
  must first ADD its failing case, an experiment runs against the existing benchmark.
- **Set the bar before you build.** For an experiment, agree the objective + tolerance up
  front (e.g. "≤ 1 pt accuracy for the cheaper model") — that's the keep/revert threshold.
- **Ask before you modify** — in place vs. new version is the user's decision, every time.
- **One hypothesis per change**, so the metric can attribute the result.
- **Label the truth, not the observed output.**
- **Never edit the eval scorer / gold to move a number.** Fix the agent.
- **The goal decides.** Keep only changes that meet their stated bar (bug fixed, or
  quality within tolerance at the target cost); revert the rest.
- **Read bounded-context data through services, never repositories.** An agent that
  needs a BC's data (e.g. `search`/`analytics`/`report` over `city_events`) depends on
  that BC's **service** — never its repository or raw SQL. Domain read rules (expiry,
  filters) live in the service; don't duplicate them in the agent. Need a read the
  service lacks? Add it to the service, and wire the service through BOTH composition
  roots (`bootstrap/agents.py` and `ai/_eval/harness.py`).
- **Don't break `base.py`.** The domain depends on the contract, not your version.
- **Record every run** — the eval CLI does this automatically (`eval_runs.jsonl`);
  cite the before/after numbers when you report the outcome.
