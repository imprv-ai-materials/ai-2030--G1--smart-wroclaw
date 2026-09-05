# `eval/category_agent/` — dataset + DeepEval loop for the category agent

The agent under test is `api/api/ai/category_agent/` — it maps an open-text
citizen report to one **primary** `ReportCategory` (+ optional **secondary**
categories). This folder is the dev-only workspace that builds a labelled
dataset, lets you enhance it in **Label Studio**, and scores the agent with
**DeepEval**. Everything runs **offline** (the agent's keyword fallback) by
default — no API key, no cost, deterministic — so the loop is fully reproducible.

Run everything from the project root (`smart_wroclaw/`) with the project venv.

```
generate_dataset.py            seed corpus → data/*.jsonl + Label Studio import + config
label_studio_to_goldens.py     Label Studio JSON export → data/category_dataset.jsonl
metrics.py                     PrimaryCategoryMatchMetric (deterministic) + per-class F1 + bootstrap CI
run_deepeval.py                the loop: run the CURRENT agent version → scores
test_category_agent_deepeval.py  CI regression gate (deepeval test run / pytest)
data/                          generated artifacts (regenerate any time)
```

## 1. Generate the dataset

```bash
python eval/category_agent/generate_dataset.py
```

Writes to `data/`: `category_dataset.jsonl` (all rows), a deterministic
stratified `dev.jsonl` / `test.jsonl` split, `label_studio_import.json`
(pre-annotated tasks), and `label_studio_config.xml` (the labelling UI).

> **Split discipline.** `dev` is for iterating; `test` is your held-out set —
> score it rarely (release checks), never tune against it. See the dev−test gap
> printed by `--split all`.

## 2. Enhance in Label Studio

1. Create a project, paste `data/label_studio_config.xml` as the labelling config.
2. Import `data/label_studio_import.json` — each task arrives **pre-annotated**
   with the seed labels as an editable *prediction*, so you review/correct rather
   than label from scratch. Turn predictions into annotations, fix the hard cases,
   add new ones from real reports, star the reference annotation as **ground truth**.
3. Export the project as **JSON** and fold it back in:

```bash
python eval/category_agent/label_studio_to_goldens.py path/to/export.json --split-out
```

There is no official Label Studio→DeepEval adapter — that script is the ~40-line
mapper (`data.text`→input, `primary`/`secondary` choices→labels).

## 3. Run the DeepEval loop → scores

```bash
python eval/category_agent/run_deepeval.py                # dev, offline baseline
python eval/category_agent/run_deepeval.py --split all    # dev + test + the gap
python eval/category_agent/run_deepeval.py --show-errors  # list misclassifications
python eval/category_agent/run_deepeval.py --llm          # OpenAI path (needs a real key + model)
```

Reports primary **accuracy with a bootstrap 95% CI**, **macro-F1**, per-class
P/R/F1, **secondary set-F1**, and top confusions. The metric is a deterministic
exact match (no LLM judge), so the score can't be gamed by wording and costs
nothing to compute.

**Baseline (offline keyword agent, v1):** dev ≈ 0.855, test ≈ 0.72. That's the
number to beat.

## 4. CI regression gate

```bash
deepeval test run eval/category_agent/test_category_agent_deepeval.py
# or: pytest eval/category_agent/test_category_agent_deepeval.py
```

Gates the **aggregate** dev accuracy against `DEV_ACCURACY_GATE` (ratchet it up
as the agent improves; never down) plus a few must-never-break smoke cases.

## 5. The optimisation loop (toward "MLZero")

`run_deepeval.py` always evaluates whatever `ai/category_agent/versions/current.yaml`
points at. So the loop is:

1. `cp -r api/api/ai/category_agent/versions/v1 …/versions/v2` and edit its
   `prompts.py` / `agent.py` (better keywords, or the LLM prompt).
2. Point `current.yaml` at `v2`, re-run `run_deepeval.py --split dev`.
3. Keep the change only if **dev** improves *and* it doesn't regress **test**
   (check `--split all`); then raise the CI gate.

This is where a coding agent (Claude Code) can drive: give it the failing
examples from `--show-errors`, let it edit `v2`, re-run the loop. **Guardrail:**
the agent may edit `versions/**` — never `eval/**` or `data/**` (the scorer and
gold labels). Keeping the scorer out of the agent's reach is what stops it
"improving" the number by editing the test instead of the agent.
