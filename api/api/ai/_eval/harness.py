"""The cross-agent evaluation engine.

One flow scores any agent on a chosen dataset, at a chosen version:

    resolve version → build agent (offline or --llm) → run each row → score

Two knobs make it work across very different agents:

  • a per-agent **adapter** (`_REGISTRY`) that knows the input field, how to build
    the agent from the shared clients/repo, and how to turn one dataset row into a
    flat `predicted` dict whose keys match the `evaluations/*.yaml` assertion fields;
  • a generic **assertion engine** that reads those fields from the gold row and the
    prediction. `field_equals` / `set_equals` roll up to accuracy; a `ranking`
    assertion switches the whole eval to IR metrics (hit@1 / MRR / recall@k).

Everything is deterministic and offline by default (the agents' keyword baselines),
so a number is reproducible and attributable to a concrete version.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

import yaml
from api.ai import load_current
from api.ai.eval_bootstrap import get_bootstrap

AI_DIR = Path(__file__).resolve().parent.parent  # api/api/ai


# ── version resolution ────────────────────────────────────────────────────────
def resolve_version(agent: str, version: str | None) -> tuple[str, type]:
    """The concrete AGENT class for `agent` at `version` (or CURRENT when None)."""
    if version is None:
        current = load_current(agent)
        return current.version, current.agent_class
    module = importlib.import_module(f"api.ai.{agent}.versions.{version}")
    return version, module.AGENT


# ── build context (shared clients / repo / helper agents) ─────────────────────
class Ctx:
    def __init__(self, use_llm: bool, dataset_dir: Path) -> None:
        self._boot = get_bootstrap()
        self.use_llm = use_llm
        self.dataset_dir = dataset_dir

    @cached_property
    def client(self):
        return self._boot.build_openai_client(self.use_llm)

    @cached_property
    def repo(self):
        # Agents that read events run against the dataset's own corpus (or empty).
        from api.ai._eval.repo import InMemoryEventsRepository

        corpus = self.dataset_dir / "corpus.jsonl"
        return InMemoryEventsRepository.from_corpus(corpus) if corpus.exists() else InMemoryEventsRepository([])

    @cached_property
    def events_service(self):
        # Agents read events through the SERVICE, never the repo — the same boundary
        # they honour in production. Wrap the corpus-backed in-memory repo in the real
        # `EventsService` so the eval exercises the true read path (filters + expiry).
        return self._boot.build_events_service(self.repo)

    @cached_property
    def extractor(self):
        # Router/report/analytics consume an EventUnderstanding; the eval feeds them
        # the real extractor's reading (CURRENT version) — an end-to-end-from-text run.
        return self._boot.build_event_extractor(use_llm=self.use_llm)

    @cached_property
    def geo(self):
        _, cls = resolve_version("geo_resolver", None)
        return cls(None)


# ── per-agent adapters ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Adapter:
    input_field: str
    build: Callable[[Ctx, type], Any]
    run: Callable[[Any, dict, Ctx], dict]
    ranking: bool = False


def _understanding_from_filters(f: dict) -> Any:
    from api.contexts_boundaries.city_events_bc.models import EventType, EventUnderstanding, ReportCategory

    return EventUnderstanding(
        type=EventType(f["type"]) if f.get("type") else None,
        secondary_types=[EventType(t) for t in f.get("secondary_types", [])],
        category=ReportCategory(f["category"]) if f.get("category") else None,
        district=f.get("district"),
        keywords=f.get("keywords", []),
    )


def _run_guardrails(agent, row, ctx):
    # `history` (optional prior turns) lets a context-only follow-up like
    # "a jednak zielony" be judged on-topic inside a running flow — rows without
    # it (the common case) pass None and behave exactly as before.
    v = agent.check(row["text"], row.get("history"))
    return {"allow": v.allow, "reason": v.reason}


def _run_router(agent, row, ctx):
    u = ctx.extractor.extract(row["text"])
    return {"intent": agent.route(row["text"], u).intent.value}


def _run_extractor(agent, row, ctx):
    u = agent.extract(row["text"])
    # `all_types` is the candidate SET (primary ∪ secondary). Asserting on the union
    # — not on `type` alone — is robust to the model swapping which reading is primary
    # (e.g. "powalone drzewo" is equally HAZARD+[ISSUE] or ISSUE+[HAZARD]); what must
    # hold is that search's type filter covers both, so the stored event is retrieved.
    all_types = sorted({t.value for t in [u.type, *u.secondary_types] if t})
    return {
        "primary_category": u.category.value if u.category else "OTHER",
        "secondary_categories": [c.value for c in u.secondary_categories],
        "all_types": all_types,
    }


def _run_report(agent, row, ctx):
    u = ctx.extractor.extract(row.get("text", ""))
    turn = agent.plan_turn(u, prior_draft=row.get("prior_draft"), fields=row.get("fields"))
    return {"expected_missing": turn.missing_fields, "expected_ready": turn.ready}


def _run_analytics(agent, row, ctx):
    u = ctx.extractor.extract(row["question"])
    # Only the EXTRACTED place is a geocode hint — never the whole question, or the
    # geocoder centroids the city and over-scopes to a tiny radius (mirrors geo_work).
    hint = u.location_text or u.address or u.district
    resolved = ctx.geo.resolve(hint) if hint else None
    scope = None
    if resolved is not None and not resolved.needs_user_location:
        scope = {"district": resolved.district, "lat": resolved.lat, "lng": resolved.lng, "radius_m": resolved.radius_m}
    answer = agent.answer(u, scope=scope)  # exercise the agent end-to-end
    return {
        "filters": {
            "type": u.type.value if u.type else None,
            "category": u.category.value if u.category else None,
        },
        "count": answer.count,
    }


def _run_geo(agent, row, ctx):
    scope = agent.resolve(row["text"])
    expected = None
    if scope is not None:
        expected = {
            "district": scope.district,
            "needs_user_location": scope.needs_user_location,
            "radius_m": scope.radius_m,
        }
    # `resolvable` is graded on every row (so "should return no scope" is testable);
    # the district / near-me fields are only graded when the gold expects a scope.
    return {"expected": expected, "resolvable": scope is not None}


_REGISTRY: dict[str, Adapter] = {
    "guardrails_agent": Adapter("text", lambda c, cls: cls(c.client), _run_guardrails),
    "router_agent": Adapter("text", lambda c, cls: cls(c.client), _run_router),
    "event_extractor": Adapter("text", lambda c, cls: cls(c.client), _run_extractor),
    "report_agent": Adapter("text", lambda c, cls: cls(c.events_service), _run_report),
    "analytics_agent": Adapter("question", lambda c, cls: cls(c.events_service, openai_client=c.client), _run_analytics),
    "geo_resolver": Adapter("text", lambda c, cls: cls(None), _run_geo),
    "search_agent": Adapter("query", lambda c, cls: cls(c.events_service), lambda a, r, c: {}, ranking=True),
}

AGENTS = list(_REGISTRY.keys())


# ── spec + dataset loading ────────────────────────────────────────────────────
@dataclass
class EvalSpec:
    name: str
    dataset: str
    assertions: list[dict]
    metrics: list[str]

    @property
    def is_ranking(self) -> bool:
        return any(a.get("kind") == "ranking" for a in self.assertions)


def load_spec(agent: str, eval_name: str | None = None) -> EvalSpec:
    eval_dir = AI_DIR / agent / "evaluations"
    files = sorted(eval_dir.glob("*.yaml"))
    if not files:
        raise SystemExit(f"{agent}: no evaluations/*.yaml spec")
    path = (eval_dir / f"{eval_name}.yaml") if eval_name else files[0]
    if not path.is_file():
        raise SystemExit(f"{agent}: no eval spec '{path.name}' (have: {', '.join(p.stem for p in files)})")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return EvalSpec(
        name=data.get("name", path.stem),
        dataset=str(data["dataset"]),
        assertions=data.get("assertions", []),
        metrics=data.get("metrics", []),
    )


def load_dataset(agent: str, dataset: str, split: str) -> list[dict]:
    path = AI_DIR / agent / "datasets" / f"{dataset}.jsonl"
    if not path.is_file():
        raise SystemExit(f"{agent}: no dataset '{dataset}.jsonl' at {path.parent}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if split != "all":
        rows = [r for r in rows if r.get("split", "dev") == split]
    return rows


def subsample(rows: list[dict], pct: int) -> list[dict]:
    """A deterministic `pct`% slice — evenly spaced across the set (not the first N),
    so a 50% sample still spans early and late rows. Reproducible: no RNG."""
    if pct >= 100 or not rows:
        return rows
    n = len(rows)
    k = max(1, round(n * pct / 100))
    return [rows[round(i * n / k)] for i in range(k)]


# ── assertion engine (classification) ─────────────────────────────────────────
def _dig(d: Any, dotted: str) -> Any:
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _passes(assertion: dict, gold_row: dict, pred: dict) -> bool | None:
    field_ = assertion["field"]
    gold_v, pred_v = _dig(gold_row, field_), _dig(pred, field_)
    if assertion.get("only_when_expected") and gold_v in (None, [], {}):
        return None  # skipped
    if assertion.get("kind") == "set_equals":
        return {str(x) for x in (gold_v or [])} == {str(x) for x in (pred_v or [])}
    return gold_v == pred_v


def score_classification(rows: list[dict], preds: list[dict], assertions: list[dict]) -> dict:
    per_assertion = {a.get("id", a["field"]): [0, 0] for a in assertions}  # [passed, graded]
    row_correct: list[bool] = []
    errors: list[dict] = []
    for row, pred in zip(rows, preds):
        ok = True
        detail = {}
        for a in assertions:
            res = _passes(a, row, pred)
            if res is None:
                continue
            key = a.get("id", a["field"])
            per_assertion[key][1] += 1
            per_assertion[key][0] += int(res)
            detail[a["field"]] = res
            ok = ok and res
        row_correct.append(ok)
        if not ok:
            errors.append({"id": row.get("id", "?"), "pred": pred, "detail": detail})
    n = len(rows) or 1
    return {
        "mode": "classification",
        "n": len(rows),
        "accuracy": sum(row_correct) / n,
        "per_assertion": {k: (p / g if g else 0.0, g) for k, (p, g) in per_assertion.items()},
        "errors": errors,
    }


# ── ranking engine (search) ───────────────────────────────────────────────────
def _ext_id_map(corpus_path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["id"]] = r.get("ext_id", str(r["id"]))
    return out


def score_ranking(agent, rows: list[dict], ctx: Ctx, k: int = 6) -> dict:
    id_to_ext = _ext_id_map(ctx.dataset_dir / "corpus.jsonl")
    hit1 = mrr = recall = 0.0
    graded = 0
    leaks = 0
    errors: list[dict] = []
    for row in rows:
        u = _understanding_from_filters(row.get("filters", {}))
        ranked = [id_to_ext.get(e.id, str(e.id)) for e in agent.search(u)]
        rel = set(row.get("relevant", []))
        excl = set(row.get("must_exclude", []))
        topk = ranked[:k]
        leaked = [e for e in topk if e in excl]
        if leaked:
            leaks += 1
        if not rel:
            continue
        graded += 1
        first = next((i + 1 for i, e in enumerate(ranked) if e in rel), None)
        h1 = 1.0 if ranked and ranked[0] in rel else 0.0
        rr = 1.0 / first if first else 0.0
        rec = len([e for e in topk if e in rel]) / len(rel)
        hit1 += h1
        mrr += rr
        recall += rec
        if h1 < 1.0 or leaked:
            errors.append({"id": row.get("id", "?"), "ranked": topk, "rank_first_rel": first, "leaked": leaked})
    g = graded or 1
    return {
        "mode": "ranking",
        "n": len(rows),
        "graded": graded,
        "k": k,
        "hit_at_1": hit1 / g,
        "mrr": mrr / g,
        "recall_at_k": recall / g,
        "exclude_leaks": leaks,
        "errors": errors,
    }


# ── top-level ─────────────────────────────────────────────────────────────────
@dataclass
class Result:
    agent: str
    version: str
    dataset: str
    split: str
    sample: int
    mode: str
    scores: dict = field(default_factory=dict)


def evaluate(
    agent: str,
    *,
    version: str | None = None,
    dataset: str | None = None,
    split: str = "dev",
    sample: int = 100,
    use_llm: bool = False,
    eval_name: str | None = None,
) -> Result:
    if agent not in _REGISTRY:
        raise SystemExit(f"unknown agent '{agent}'. Known: {', '.join(AGENTS)}")
    adapter = _REGISTRY[agent]
    spec = load_spec(agent, eval_name)
    dataset = dataset or spec.dataset
    rows = subsample(load_dataset(agent, dataset, split), sample)
    resolved_version, agent_class = resolve_version(agent, version)
    ctx = Ctx(use_llm=use_llm, dataset_dir=AI_DIR / agent / "datasets")
    agent_obj = adapter.build(ctx, agent_class)

    if adapter.ranking:
        scores = score_ranking(agent_obj, rows, ctx)
    else:
        preds = [adapter.run(agent_obj, row, ctx) for row in rows]
        scores = score_classification(rows, preds, spec.assertions)

    return Result(
        agent=agent,
        version=resolved_version,
        dataset=dataset,
        split=split,
        sample=sample,
        mode=scores["mode"],
        scores=scores,
    )


def summary_metrics(result: Result) -> dict:
    """The headline scalars for the history ledger — mode-specific."""
    s = result.scores
    if result.mode == "ranking":
        return {
            "hit_at_1": round(s["hit_at_1"], 4),
            "mrr": round(s["mrr"], 4),
            "recall_at_k": round(s["recall_at_k"], 4),
            "exclude_leaks": s["exclude_leaks"],
            "graded": s["graded"],
        }
    return {"accuracy": round(s["accuracy"], 4)}
