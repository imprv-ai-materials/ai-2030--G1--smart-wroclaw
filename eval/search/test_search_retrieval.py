"""CI regression gate for the chat search tool.

Runs outside the default `pypyr test` (which scopes to `api/tests`); invoke it
explicitly, the same way as the category eval:

    pytest eval/search/test_search_retrieval.py

It gates the AGGREGATE dev retrieval quality against a floor (ratchet the floor
up as search improves — never down) plus a handful of must-never-break smoke
cases. The two `xfail`s below are the live weaknesses this dataset was built to
drive out — when the search fix lands they flip to XPASS, and you promote them to
hard assertions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api.contexts_boundaries.city_events_bc.services.events import EventsService  # noqa: E402
from memory_repo import InMemoryEventsRepository  # noqa: E402
from metrics import aggregate  # noqa: E402
from run_eval import DATA_DIR, _ext_id_map, _load_queries, _run  # noqa: E402

K = 6

# Floors — the current offline baseline. Raise as search improves; never lower.
DEV_MRR_GATE = 0.70
DEV_RECALL_GATE = 1.00


def _service() -> EventsService:
    return EventsService(InMemoryEventsRepository.from_corpus(DATA_DIR / "corpus.jsonl"))


def _score_all(split: str):
    service = _service()
    ext = _ext_id_map(DATA_DIR / "corpus.jsonl")
    return [_run(service, ext, q, K) for q in _load_queries(split)]


def _by_id(split: str):
    return {s.id: s for s in _score_all(split)}


def test_dev_aggregate_does_not_regress() -> None:
    agg = aggregate(_score_all("dev"))
    assert agg.mrr >= DEV_MRR_GATE, f"dev MRR {agg.mrr:.3f} < gate {DEV_MRR_GATE}"
    assert agg.recall_at_k >= DEV_RECALL_GATE, f"dev Recall@{K} {agg.recall_at_k:.3f} regressed"


@pytest.mark.parametrize(
    "query_id",
    ["krzyki-water-main", "flood-odra", "nadodrze-streetlight", "diacritics-gadow"],
)
def test_smoke_target_ranks_first(query_id: str) -> None:
    # Must-never-break: for these the correct event already tops the results.
    s = _by_id("dev")[query_id]
    assert s.hit_at_1 == 1.0, f"{query_id}: target fell out of rank #1 → {s.ranked[:K]}"


@pytest.mark.xfail(reason="known weakness: keyword is discarded, so the target is buried")
def test_target_at_top_for_keyword_queries() -> None:
    # When a discriminating keyword ('kot', 'prąd', 'Sky Tower') is present, the
    # matching event should rank #1 — today it doesn't, because structured facets
    # drop `q`. This is the number to move.
    dev = _by_id("dev")
    assert dev["missing-cat"].hit_at_1 == 1.0
    assert dev["power-outage"].hit_at_1 == 1.0
    assert dev["sky-tower-promo"].hit_at_1 == 1.0


@pytest.mark.xfail(reason="known bug: search does not filter status, so RESOLVED events leak")
def test_no_resolved_events_leak() -> None:
    # A RESOLVED report must never surface as a live search result.
    scores = _score_all("dev") + _score_all("test")
    leaked = {s.id: s.exclude_leaks for s in scores if s.exclude_leaks}
    assert not leaked, f"resolved/closed events leaked: {leaked}"
