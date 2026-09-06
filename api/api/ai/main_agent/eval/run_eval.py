"""Score the chat SEARCH tool against the labelled retrieval dataset.

    python api/api/ai/main_agent/eval/run_eval.py                 # dev split
    python api/api/ai/main_agent/eval/run_eval.py --split all      # dev + test + the gap
    python api/api/ai/main_agent/eval/run_eval.py --show-errors    # per-query failures
    python api/api/ai/main_agent/eval/run_eval.py --k 6            # top-k window (default 6 = chat cards)

It runs the REAL pipeline offline: each query's gold reading →
`to_search_filters` → `EventsService.list_events` over an in-memory corpus, then
scores the ranked output with deterministic IR metrics (Hit@1, MRR, Recall@k,
false-positive counts, must-exclude leaks). No API key, no Postgres, no cost.

Queries carry the *gold* structured reading (`filters`), so this isolates
ranking/matching from extraction noise — the number here moves only when the
search projection or the ordering changes, which is what we want to improve.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # repo root (…/api/api/ai/main_agent/eval)
sys.path.insert(0, str(ROOT / "api"))  # make `api` importable from any CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))  # local metrics/memory_repo
DATA_DIR = Path(__file__).resolve().parents[1] / "datasets"  # the agent's datasets/

from api.ai.eval_bootstrap import get_bootstrap  # noqa: E402
from api.contexts_boundaries.city_events_bc.models import (  # noqa: E402
    EventType,
    EventUnderstanding,
    ReportCategory,
    to_search_filters,
)
from api.contexts_boundaries.city_events_bc.services.events import EventsService  # noqa: E402
from memory_repo import InMemoryEventsRepository  # noqa: E402
from metrics import Aggregate, aggregate, score_query  # noqa: E402


def _load_queries(split: str) -> list[dict]:
    rows = [
        json.loads(line)
        for line in (DATA_DIR / "queries.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return rows if split == "all" else [r for r in rows if r.get("split") == split]


def _understanding(filters: dict) -> EventUnderstanding:
    """Rebuild the gold structured reading as the extractor would emit it."""
    return EventUnderstanding(
        type=EventType(filters["type"]) if filters.get("type") else None,
        category=ReportCategory(filters["category"]) if filters.get("category") else None,
        district=filters.get("district"),
        keywords=filters.get("keywords", []),
    )


def _run(service: EventsService, ext_by_id: dict[int, str], query: dict, k: int):
    u = _understanding(query["filters"])
    filters = to_search_filters(u)
    results = service.list_events(**filters)
    ranked = [ext_by_id[e.id] for e in results]
    return score_query(
        id=query["id"],
        ranked=ranked,
        relevant=query.get("relevant", []),
        hard_negatives=query.get("hard_negatives", []),
        must_exclude=query.get("must_exclude", []),
        difficulty=query.get("difficulty", ""),
        split=query.get("split", ""),
        k=k,
    )


def _print_report(title: str, agg: Aggregate) -> None:
    print(f"\n=== {title} — {agg.n_graded} graded queries (k={agg.k}) ===")
    print(f"  Hit@1                  {agg.hit_at_1:.3f}   (relevant event ranked #1)")
    print(f"  MRR                    {agg.mrr:.3f}   (1 / rank of first relevant)")
    print(f"  Recall@{agg.k}              {agg.recall_at_k:.3f}   (relevant events inside the window)")
    print(f"  Clean top-1            {agg.clean_top1:.3f}   (top result relevant, not a distractor)")
    print(f"  Hard-negs in top-{agg.k}      {agg.mean_hard_neg_in_k:.2f}   (planted false positives shown)")
    print(f"  Hard-negs above rel.   {agg.mean_hard_neg_above_relevant:.2f}   (distractors crowding out the target)")
    print(f"  Must-exclude leaks     {agg.exclude_violations}      (RESOLVED/closed surfaced — want 0)")
    print(f"  Clean misses           {agg.misses}      (nothing relevant in the window)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--k", type=int, default=6, help="top-k window (chat shows 6 cards)")
    ap.add_argument("--show-errors", action="store_true", help="list per-query failures")
    args = ap.parse_args()

    repo = InMemoryEventsRepository.from_corpus(DATA_DIR / "corpus.jsonl")
    # Through the eval container — the one place that knows EventsService is the
    # search code path (offline: no config, no Postgres — see eval_bootstrap).
    service = get_bootstrap().build_events_service(repo)
    ext_by_id = _ext_id_map(DATA_DIR / "corpus.jsonl")

    def run_split(split: str):
        scores = [_run(service, ext_by_id, q, args.k) for q in _load_queries(split)]
        return scores

    if args.split == "all":
        dev, test = run_split("dev"), run_split("test")
        _print_report("DEV", aggregate(dev))
        _print_report("TEST", aggregate(test))
        gap = aggregate(dev).mrr - aggregate(test).mrr
        print(f"\n  dev−test MRR gap: {gap:+.3f}")
        scores = dev + test
    else:
        scores = run_split(args.split)
        _print_report(args.split.upper(), aggregate(scores))

    if args.show_errors:
        print("\n--- per-query (failures first) ---")
        for s in sorted(scores, key=lambda x: (x.hit_at_1, x.recall_at_k)):
            flag = ""
            if s.exclude_leaks:
                flag = f"  ✖ leaked {','.join(s.exclude_leaks)}"
            elif s.graded and s.recall_at_k == 0:
                flag = "  ✖ MISS (target not in window)"
            elif s.graded and not s.hit_at_1:
                flag = f"  ▲ target at rank {s.rank_of_first_relevant}"
            print(f"  {s.id:24} {json.dumps(s.as_row(), ensure_ascii=False)}{flag}")
            print(f"      ranked: {s.ranked[: args.k]}")


def _ext_id_map(path: Path) -> dict[int, str]:
    """Map each corpus event's numeric id → its stable `ext_id` (evt-NN)."""
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["id"]] = row["ext_id"]
    return out


if __name__ == "__main__":
    main()
