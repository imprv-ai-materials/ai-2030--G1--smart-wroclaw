---
name: agent-improve
description: Dataset-first process for improving any api/api/ai agent after finding a failure (e.g. in a chat/conversation, a bug report, or your own testing). Use BEFORE changing any agent prompt, heuristic, projection, or code. Enforces the rule that every agent enhancement must first capture the failing case in that agent's dataset, then fix, then re-run the eval to prove it and prevent regressions.
---

# Improving an agent (dataset-first)

The iron rule: **never "just fix the code."** Every enhancement starts by capturing
the failing case in the agent's dataset, so the fix is measurable and can't silently
regress later. The loop is: **find the failure → add it to the dataset → fix → prove
it with the eval → record the run.**

The agents live under `api/api/ai/<agent>/` — `guardrails_agent`, `router_agent`,
`event_extractor`, `search_agent`, `report_agent`, `analytics_agent`, `geo_resolver`,
and the composed `main_agent`. Each has `datasets/`, `evaluations/*.yaml`, and
`versions/`.

## When to use
A resident (or you) hit a turn where an agent answered wrong or weakly — in a live
chat, a reported bug, or testing. Invoke this BEFORE touching any prompt/heuristic/code.

## The loop

1. **Locate the failing turn(s).** From a chat, read the conversation from Postgres:
   `chat_conversations` / `chat_messages` (each assistant row's `data.intent` tells you
   which lane ran). `?chat=<id>` in the UI is that `conversation_id`. Identify **which
   agent** produced the bad output — trace it through the pipeline (guardrails → extractor
   → router → the lane). A wrong answer often originates *upstream* of where it shows.

2. **Turn each failure into a gold case** and ADD it to that agent's dataset
   (`api/api/ai/<agent>/datasets/<name>.jsonl`): the input exactly as the resident typed
   it, plus the **correct expected output** (the label — what SHOULD happen, not what the
   agent did). Mark traps with `difficulty: hard` and a `note` citing where it came from
   (e.g. "chat 3"). Use the annotator if it helps:
   `pypyr annotate agent=<agent> dataset=<name>`.

3. **Baseline it (red).** `pypyr eval agent=<agent>` — the new case should FAIL, proving
   it captures the bug. (The run is appended to `ai/<agent>/eval_runs.jsonl`.)

4. **Fix the smallest thing** that turns it green: a prompt (`versions/vN/prompts.py`), a
   heuristic / projection, or deterministic code. For prompt/behaviour changes prefer a
   **new version** (`cp -r versions/v1 versions/v2`, edit, then flip
   `versions/current.yaml`) so you can compare v1 vs v2.

5. **Prove it (green, no regression).** `pypyr eval agent=<agent> version=<new>` — the new
   case passes AND the rest don't regress (`pypyr eval agent=<agent> split=all`). Compare
   against history: `pypyr eval agent=<agent> history=1`.

6. **Guard the boundary.** If the failure spanned agents (e.g. the extractor emitted a bad
   field the analytics agent then trusted), add the case at **each** layer it touched — the
   extractor's dataset AND the downstream agent's — not only the last one.

## Rules
- **Dataset before code, always.** No enhancement without a new dataset case first.
- **Label the truth, not the observed output.**
- **Never edit the eval scorer / gold to make a number go up.** Fix the agent.
- **Offline first.** The keyword baseline is what you must beat; `llm=1` is the ceiling.
- **Record every run** — the eval CLI does this automatically (`eval_runs.jsonl`).
