# `event_extractor/eval/` — dataset + DeepEval loop for the extractor

The agent under test is `api/api/ai/event_extractor/` — it reads an open-text
citizen message into a structured `EventUnderstanding`; this loop scores its
**category** field (one **primary** `ReportCategory` + optional **secondary**
categories). The runnable loop lives here (`eval/`); the labelled gold lives in
the agent's [`../datasets/`](../datasets). Everything runs **offline** (the
agent's keyword fallback) by default — no API key, no cost, deterministic — so
the loop is fully reproducible.

Run everything from the project root (`smart_wroclaw/`) with the project venv.

```
eval/generate_dataset.py                  seed corpus → ../datasets/*.jsonl (deterministic split)
eval/metrics.py                           PrimaryCategoryMatchMetric (deterministic) + per-class F1 + bootstrap CI
eval/run_deepeval.py                      the loop: run the CURRENT agent version → scores
eval/test_event_extractor_deepeval.py     CI regression gate (deepeval test run / pytest)
../datasets/category_dataset.jsonl        all rows (+ dev.jsonl / test.jsonl split)
../datasets/annotate.template.js          the /.annotator template for this dataset
```

## 1. Generate the dataset

```bash
python api/api/ai/event_extractor/eval/generate_dataset.py
```

Writes to `../datasets/`: `category_dataset.jsonl` (all rows) plus a
deterministic stratified `dev.jsonl` / `test.jsonl` split.

> **Split discipline.** `dev` is for iterating; `test` is your held-out set —
> score it rarely (release checks), never tune against it. See the dev−test gap
> printed by `--split all`. The split is deterministic (no RNG) and assigned by
> this generator, not by hand.

## 2. Review / edit the labels

Use the in-repo annotator ([`/.annotator`](../../../../../.annotator/README.md)) —
edits the dataset in place, no extra service:

```bash
python .annotator/annotate.py \
  api/api/ai/event_extractor/datasets/annotate.template.js \
  api/api/ai/event_extractor/datasets/dev.jsonl
# → http://127.0.0.1:7900
```

## 3. Run the DeepEval loop → scores

```bash
python api/api/ai/event_extractor/eval/run_deepeval.py                # dev, offline baseline
python api/api/ai/event_extractor/eval/run_deepeval.py --split all    # dev + test + the gap
python api/api/ai/event_extractor/eval/run_deepeval.py --show-errors  # list misclassifications
python api/api/ai/event_extractor/eval/run_deepeval.py --llm          # OpenAI path (needs a real key + model)
```

Reports primary **accuracy with a bootstrap 95% CI**, **macro-F1**, per-class
P/R/F1, **secondary set-F1**, and top confusions. The metric is a deterministic
exact match (no LLM judge), so the score can't be gamed by wording and costs
nothing to compute.

**Baseline (offline keyword agent, v1):** dev ≈ 0.855, test ≈ 0.72. That's the
number to beat.

## 4. CI regression gate

```bash
deepeval test run api/api/ai/event_extractor/eval/test_event_extractor_deepeval.py
# or: pytest api/api/ai/event_extractor/eval/test_event_extractor_deepeval.py
```

Gates the **aggregate** dev accuracy against `DEV_ACCURACY_GATE` (ratchet it up
as the agent improves; never down) plus a few must-never-break smoke cases.

## 5. The optimisation loop (toward "MLZero")

`run_deepeval.py` always evaluates whatever `event_extractor/versions/current.yaml`
points at. So the loop is:

1. `cp -r api/api/ai/event_extractor/versions/v1 …/versions/v2` and edit its
   `prompts.py` / `agent.py` (better keywords, or the LLM prompt).
2. Point `current.yaml` at `v2`, re-run `run_deepeval.py --split dev`.
3. Keep the change only if **dev** improves *and* it doesn't regress **test**
   (check `--split all`); then raise the CI gate.

This is where a coding agent (Claude Code) can drive: give it the failing
examples from `--show-errors`, let it edit `v2`, re-run the loop. **Guardrail:**
the agent may edit `versions/**` — never this `eval/` scorer or the `../datasets/`
gold. Keeping the scorer out of the agent's reach is what stops it "improving" the
number by editing the test instead of the agent.
