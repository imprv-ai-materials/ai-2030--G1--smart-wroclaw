"""Unified evaluation CLI — score any agent, at any version, on a chosen dataset.

    python api/api/ai/evaluate.py --list
    python api/api/ai/evaluate.py --agent guardrails_agent
    python api/api/ai/evaluate.py --agent router_agent --version v1 --split all
    python api/api/ai/evaluate.py --agent event_extractor --dataset category_dataset --sample 50 --llm
    python api/api/ai/evaluate.py --agent search_agent --show-errors
    python api/api/ai/evaluate.py --agent guardrails_agent --history

Reads the agent's `evaluations/*.yaml` spec, builds it at `--version` (CURRENT when
omitted), runs `--sample`% of its dataset (`--split dev|test|all`), prints scores,
and appends the run to the agent's `eval_runs.jsonl` history (disable with
`--no-store`). Offline by default (each agent's keyword baseline); `--llm` uses the
OpenAI path. Prefer `pypyr eval agent=<name> …`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repo root (…/api/api/ai/evaluate.py)
sys.path.insert(0, str(ROOT / "api"))  # make `api` importable from any CWD

from api.ai._eval import history  # noqa: E402
from api.ai._eval.harness import AGENTS, AI_DIR, Result, evaluate, load_spec, summary_metrics  # noqa: E402

# pypyr forwards every var, so "unset" arrives as one of these sentinels.
_UNSET = ("", "current", "auto", "default", "none")


def _opt(value: str | None) -> str | None:
    return None if value is None or value.strip().lower() in _UNSET else value


def _print(result: Result) -> None:
    s = result.scores
    print(
        f"\n=== {result.agent} @ {result.version}  ·  dataset={result.dataset}  ·  split={result.split}"
        f"  ·  sample={result.sample}%  ·  n={s['n']} ==="
    )
    if result.mode == "ranking":
        print(f"  graded             {s['graded']}")
        print(f"  Hit@1              {s['hit_at_1']:.3f}")
        print(f"  MRR                {s['mrr']:.3f}")
        print(f"  Recall@{s['k']}           {s['recall_at_k']:.3f}")
        print(f"  Must-exclude leaks {s['exclude_leaks']}")
    else:
        print(f"  Accuracy           {s['accuracy']:.3f}")
        for key, (rate, graded) in s["per_assertion"].items():
            print(f"    {key:26} {rate:.3f}  (graded {graded})")


def _print_errors(result: Result) -> None:
    errors = result.scores.get("errors", [])
    print(f"\n  --- failures ({len(errors)}) ---" if errors else "\n  (no failures)")
    for e in errors:
        print(f"   {e}")


def _print_history(agent: str) -> None:
    runs = history.load_runs(AI_DIR, agent)
    if not runs:
        print(f"{agent}: no runs recorded yet ({history.ledger_path(AI_DIR, agent)})")
        return
    print(f"\n=== {agent} — {len(runs)} recorded runs ===")
    print(f"  {'when':20} {'ver':5} {'dataset':16} {'split':5} {'sample':>6}  metrics")
    for r in runs:
        metrics = " ".join(f"{k}={v}" for k, v in r.get("metrics", {}).items())
        print(
            f"  {r.get('ts', ''):20} {r.get('version', ''):5} {r.get('dataset', ''):16} "
            f"{r.get('split', ''):5} {str(r.get('sample', '')) + '%':>6}  {metrics}"
        )


def _list() -> None:
    print("agents (run: pypyr eval agent=<name> [version=v2] [dataset=D] [split=dev|test|all] [sample=50] [llm=1]):\n")
    for agent in AGENTS:
        datasets = sorted(p.stem for p in (AI_DIR / agent / "datasets").glob("*.jsonl"))
        try:
            spec = load_spec(agent)
            print(f"  {agent:18} eval={spec.name:14} default-dataset={spec.dataset:18} jsonl={datasets}")
        except SystemExit as exc:
            print(f"  {agent:18} (no spec: {exc})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Unified agent evaluation runner")
    ap.add_argument("--agent", choices=AGENTS)
    ap.add_argument("--version", default=None, help="pin a version (e.g. v2); default = current.yaml")
    ap.add_argument("--dataset", default=None, help="dataset stem under the agent's datasets/ (default: the spec's)")
    ap.add_argument("--eval", dest="eval_name", default=None, help="which evaluations/<name>.yaml (default: first)")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--sample", type=int, default=100, help="percent of the (split) dataset to run, 1–100")
    ap.add_argument("--llm", action="store_true", help="use the OpenAI path instead of the offline baseline")
    ap.add_argument("--show-errors", action="store_true", help="list per-row failures")
    ap.add_argument("--no-store", action="store_true", help="don't append this run to the agent's history")
    ap.add_argument("--history", action="store_true", help="print the agent's recorded runs and exit")
    ap.add_argument("--list", action="store_true", help="list agents + their eval specs/datasets")
    args = ap.parse_args()

    if args.list or not args.agent:
        _list()
        return
    if args.history:
        _print_history(args.agent)
        return

    sample = max(1, min(100, args.sample))
    result = evaluate(
        args.agent,
        version=_opt(args.version),
        dataset=_opt(args.dataset),
        split=args.split,
        sample=sample,
        use_llm=args.llm,
        eval_name=_opt(args.eval_name),
    )
    _print(result)
    if args.show_errors:
        _print_errors(result)

    if not args.no_store:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "agent": result.agent,
            "version": result.version,
            "dataset": result.dataset,
            "split": result.split,
            "sample": result.sample,
            "mode": result.mode,
            "metrics": summary_metrics(result),
        }
        path = history.append_run(AI_DIR, result.agent, record)
        print(f"\n  ↳ recorded to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
