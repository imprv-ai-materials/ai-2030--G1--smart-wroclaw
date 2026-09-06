# `main_agent/eval/` — retrieval dataset + loop for the chat search tool

The thing under test is the main agent's (orchestrator's) **search** path: a
resident types a natural message, the orchestrator reads it into filters
(`to_search_filters`) and calls `EventsService.list_events`, and the top results
are shown on the map + as cards. The complaint this dataset exists to fix: **weak
matching — false positives, and the event you wanted isn't at the top.**

The runnable loop lives here (`eval/`); the labelled gold + fixed corpus live in
the agent's [`../datasets/`](../datasets). It runs **fully offline** — no API
key, no Postgres, no cost — so the loop is reproducible.

```
eval/build_corpus.py          fake_events.json → ../datasets/corpus.jsonl (stable ids + created_at)
eval/memory_repo.py           in-memory events repo → drives the real search offline
eval/metrics.py               Hit@1 · MRR · Recall@k · false-positive counts · exclude leaks
eval/run_eval.py              run the CURRENT search over the corpus → scores
eval/test_search_retrieval.py CI regression gate (floors + smoke + the two xfails to fix)
datasets/corpus.jsonl         the fixed "documents" search runs against (38 events)
datasets/queries.jsonl        THE DATASET — labelled resident searches
datasets/annotate.template.js the /.annotator template for this dataset
```

## The dataset (`../datasets/queries.jsonl`)

One JSON object per line. Each is a resident search with its gold labels:

| field            | meaning                                                             |
|------------------|---------------------------------------------------------------------|
| `query`          | the raw message a resident types                                    |
| `filters`        | the **gold** structured reading (`type`/`category`/`district`/`keywords`) the extractor should emit — lets the eval score ranking in isolation from extraction noise |
| `relevant`       | events that genuinely answer the query — should rank **at the top** |
| `acceptable`     | fine to show; neither required nor penalised                        |
| `hard_negatives` | tempting-but-wrong events (same type/category/district, different subject) — must **not** crowd the top |
| `must_exclude`   | events that must **not** surface at all (e.g. a RESOLVED report)    |
| `difficulty` / `note` | curation metadata                                              |
| `split`          | `dev` / `test` — **assigned automatically** by the dataset pipeline, not by hand |

The queries deliberately probe the known failure modes: a discriminating keyword
that a facet filter throws away (`missing-cat`, `power-outage`, `sky-tower-promo`),
diacritic folding (`diacritics-gadow` — `gadow` → `Gądów`), token collisions
(`swidnicka-closed`, `bridge-grunwaldzki`, `aggressive-dog`'s `pies`), a
RESOLVED-only match that should return nothing (`overflow-bins-rynek`), and
multi-target recall (`whats-on-weekend`, `promotions`, `roadworks-closures`).

> **Split discipline.** `dev` is for iterating; `test` is held out — score it
> rarely, never tune against it. `run_eval.py --split all` prints the dev−test gap.

## Review / edit the gold

Use the in-repo annotator ([`/.annotator`](../../../../../.annotator/README.md)) —
a drag-cards-into-buckets UI shaped for this exact task, editing the dataset in
place:

```bash
python .annotator/annotate.py \
  api/api/ai/main_agent/datasets/annotate.template.js \
  api/api/ai/main_agent/datasets/queries.jsonl
# → http://127.0.0.1:7900
```

## Run the loop → scores

```bash
python api/api/ai/main_agent/eval/run_eval.py                 # dev split
python api/api/ai/main_agent/eval/run_eval.py --split all      # dev + test + the gap
python api/api/ai/main_agent/eval/run_eval.py --show-errors    # per-query failures + the ranked output
python api/api/ai/main_agent/eval/run_eval.py --k 6            # top-k window (chat shows 6 cards)
```

### Metrics

Search is ranking, so it's scored like retrieval — all deterministic (no LLM
judge), so the number can't be gamed by wording and costs nothing:

- **Hit@1** — a relevant event is ranked #1 (directly measures "at the top").
- **MRR** — 1 / rank of the first relevant event.
- **Recall@k** — relevant events landing inside the window the resident sees.
- **Hard-negs in top-k / above relevant** — planted false positives shown, and
  how many crowd out the target.
- **Must-exclude leaks** — RESOLVED/closed events that surfaced (want 0).

### Baseline (current search, offline) — the number to beat

```
DEV (18 graded queries, k=6):  Hit@1 0.500 · MRR 0.704 · Recall@6 1.000
                               hard-negs in top-6 0.72 · must-exclude leaks 1
```

Two root causes the baseline exposes:

1. **The keyword is discarded.** `to_search_filters` drops the free-text `q`
   whenever any structured facet is set, so a query like *"zaginął mi **kot**"*
   becomes "all MISSING_PET, newest first" — the lost cat lands last, behind a
   lost dog and a **RESOLVED** found cat. Ranking is pure `created_at DESC`, with
   no relevance signal, so the target is buried.
2. **Status isn't filtered.** The chat search calls `list_events` without a
   status, so RESOLVED/SCHEDULED events leak into results.

## CI regression gate

```bash
pytest api/api/ai/main_agent/eval/test_search_retrieval.py
```

Gates aggregate **dev** MRR/Recall against a floor (ratchet up as search
improves; never down) plus must-never-break smoke cases. Two tests are
`xfail`ed — they encode the weaknesses above; when the search fix lands they flip
to **XPASS** and you promote them to hard assertions and raise the floor.

## The optimisation loop

`run_eval.py` scores whatever the current search code does. So the loop is:

1. Improve the search projection / ranking in
   `api/api/contexts_boundaries/city_events_bc/` (keep keywords as a ranking
   signal, add relevance scoring + diacritic-folded token matching, filter
   status) — **not** here.
2. Re-run `run_eval.py --split dev`; keep the change only if dev improves *and*
   `--split all` shows no test regression; then ratchet the gate.

**Guardrail:** the fix may edit the search code under `api/api/contexts_boundaries/**`
— never this `eval/` scorer or the `../datasets/` gold. Keeping the scorer out of
the agent's reach is what stops it "improving" the number by editing the test.
