"""Run the DeepEval loop for event_extractor and print scores.

    python api/api/ai/event_extractor/eval/run_deepeval.py                 # dev split, offline
    python api/api/ai/event_extractor/eval/run_deepeval.py --split test     # held-out (touch rarely!)
    python api/api/ai/event_extractor/eval/run_deepeval.py --split all      # dev + test + the gap
    python api/api/ai/event_extractor/eval/run_deepeval.py --llm            # use the OpenAI path

By default it evaluates the OFFLINE keyword baseline (no API key, no cost,
deterministic) — that is the number to beat. `--llm` swaps in the OpenAI path
(needs a valid CONFIG__OPENAI__API_KEY and a real model; the repo default
`gpt-5.4` is a placeholder, so set a real one first).

Which agent version runs is whatever `ai/category_agent/versions/current.yaml`
points at — so promoting v2 and re-running this is the whole optimisation loop.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Keep DeepEval fully offline: no telemetry, no error-reporting phone-home.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "NO")
os.environ.setdefault("DEEPEVAL_DISABLE_PROGRESS_BAR", "YES")

ROOT = Path(__file__).resolve().parents[5]  # repo root (…/api/api/ai/event_extractor/eval)
sys.path.insert(0, str(ROOT / "api"))  # make `api` importable from any CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))  # local metrics.py
DATA_DIR = Path(__file__).resolve().parents[1] / "datasets"  # the agent's datasets/

from api.ai.eval_bootstrap import get_bootstrap  # noqa: E402
from api.contexts_boundaries.city_events_bc.models import ReportCategory  # noqa: E402
from metrics import (  # noqa: E402
    PrimaryCategoryMatchMetric,
    bootstrap_ci,
    macro_f1,
    per_class_prf,
    secondary_set_f1,
)

LABELS = [c.value for c in ReportCategory]


def _load(split: str) -> list[dict]:
    path = DATA_DIR / f"{split}.jsonl"
    if not path.is_file():
        sys.exit(f"missing {path} — run: python api/api/ai/event_extractor/eval/generate_dataset.py")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_agent(use_llm: bool):
    # The eval container resolves the CURRENT version + the offline/LLM client;
    # here we only report which of the two actually ran (an LLM run silently
    # degrades to offline when no key is configured — `is_configured` is False).
    bootstrap = get_bootstrap()
    agent = bootstrap.build_event_extractor(use_llm=use_llm)
    version = bootstrap.current_version("event_extractor")
    mode = "llm" if bootstrap.build_openai_client(use_llm).is_configured else "offline-keyword"
    return agent, version, mode


def _evaluate_split(split: str, use_llm: bool) -> dict:
    from deepeval import evaluate
    from deepeval.evaluate.configs import AsyncConfig, CacheConfig, DisplayConfig, ErrorConfig
    from deepeval.test_case import LLMTestCase

    rows = _load(split)
    agent, version, mode = _build_agent(use_llm)

    test_cases: list[LLMTestCase] = []
    expected_primary: list[str] = []
    predicted_primary: list[str] = []
    primary_scores: list[float] = []
    secondary_f1s: list[float] = []

    for r in rows:
        result = agent.extract(r["text"])
        pred = result.category.value if result.category else "OTHER"
        gold = r["primary_category"]
        expected_primary.append(gold)
        predicted_primary.append(pred)
        primary_scores.append(1.0 if pred == gold else 0.0)
        secondary_f1s.append(
            secondary_set_f1(r.get("secondary_categories", []), [c.value for c in result.secondary_categories])
        )
        test_cases.append(LLMTestCase(input=r["text"], actual_output=pred, expected_output=gold))

    # --- the DeepEval loop proper: score the test cases with our metric ---
    metric = PrimaryCategoryMatchMetric()
    try:
        evaluate(
            test_cases=test_cases,
            metrics=[metric],
            hyperparameters={"agent_version": version, "mode": mode, "split": split},
            async_config=AsyncConfig(run_async=False),
            cache_config=CacheConfig(write_cache=False, use_cache=False),
            display_config=DisplayConfig(show_indicator=False, print_results=False),
            error_config=ErrorConfig(ignore_errors=True),
        )
    except Exception as exc:  # never let telemetry / platform hiccups block scoring
        print(f"  [warn] deepeval.evaluate() reporting step skipped: {exc}")

    acc, lo, hi = bootstrap_ci(primary_scores)
    per_class = per_class_prf(expected_primary, predicted_primary, LABELS)
    sec_mean = sum(secondary_f1s) / len(secondary_f1s) if secondary_f1s else 0.0

    return {
        "split": split,
        "version": version,
        "mode": mode,
        "n": len(rows),
        "accuracy": acc,
        "ci": (lo, hi),
        "macro_f1": macro_f1(per_class),
        "secondary_f1": sec_mean,
        "per_class": per_class,
        "expected": expected_primary,
        "predicted": predicted_primary,
        "rows": rows,
    }


def _confusions(res: dict) -> list[tuple[str, str, int]]:
    counts: dict[tuple[str, str], int] = {}
    for e, p in zip(res["expected"], res["predicted"]):
        if e != p:
            counts[(e, p)] = counts.get((e, p), 0) + 1
    return sorted(((e, p, n) for (e, p), n in counts.items()), key=lambda t: -t[2])


def _print_report(res: dict) -> None:
    lo, hi = res["ci"]
    print(f"\n── {res['split'].upper()}  (agent=category_agent {res['version']}, mode={res['mode']}, n={res['n']}) ──")
    print(f"  primary accuracy  : {res['accuracy']:.3f}   95% CI [{lo:.3f}, {hi:.3f}]  (bootstrap)")
    print(f"  macro-F1 (primary): {res['macro_f1']:.3f}")
    print(f"  secondary set-F1  : {res['secondary_f1']:.3f}")
    print(f"  {'class':<17}{'P':>6}{'R':>6}{'F1':>6}{'n':>5}")
    for c in LABELS:
        m = res["per_class"][c]
        if m["support"]:
            print(f"  {c:<17}{m['precision']:>6.2f}{m['recall']:>6.2f}{m['f1']:>6.2f}{m['support']:>5}")


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepEval loop for category_agent")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--llm", action="store_true", help="use the OpenAI path instead of the offline baseline")
    ap.add_argument("--show-errors", action="store_true", help="print misclassified examples")
    args = ap.parse_args()

    splits = ["dev", "test"] if args.split == "all" else [args.split]
    results = {s: _evaluate_split(s, args.llm) for s in splits}

    for s in splits:
        res = results[s]
        _print_report(res)
        conf = _confusions(res)
        if conf:
            top = ", ".join(f"{e}→{p}×{n}" for e, p, n in conf[:6])
            print(f"  top confusions    : {top}")
        if args.show_errors:
            for r, e, p in zip(res["rows"], res["expected"], res["predicted"]):
                if e != p:
                    print(f"    [{r['id']} {r['difficulty']}] {e}→{p} :: {r['text']}")

    if args.split == "all":
        gap = results["dev"]["accuracy"] - results["test"]["accuracy"]
        print(
            f"\n  dev−test accuracy gap: {gap:+.3f}  "
            f"(large positive gap ⇒ overfitting to dev; near-zero ⇒ generalising)"
        )


if __name__ == "__main__":
    main()
