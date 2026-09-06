"""Deterministic retrieval metrics for the search eval — no LLM judge.

Search is ranking, so we score it the way IR is scored: does a *relevant* event
land at the top, are all of them within the window the resident actually sees,
and do the known distractors stay out. Every metric is a pure function of the
ranked `ext_id` list and the query's gold labels, so the score is reproducible
and can't be gamed by wording.

Label sets on a query:
  • relevant       — the events the resident is looking for (should rank at top)
  • acceptable     — fine to show; neither required nor penalised
  • hard_negatives — tempting-but-wrong; must not crowd the top / ideally excluded
  • must_exclude   — must NOT surface at all (e.g. a RESOLVED report)

An event counts as a *false positive* only if it is a hard_negative or a
must_exclude — unlabelled events are treated as neutral, so precision measures
the distractors we deliberately planted, which is exactly the "false positives"
the ranking is meant to suppress.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QueryScore:
    id: str
    difficulty: str
    split: str
    ranked: list[str]                      # search output, best-first (ext_ids)
    relevant: set[str]
    hard_negatives: set[str]
    must_exclude: set[str]
    k: int

    # computed
    graded: bool = True                    # False for pure must-exclude queries
    rank_of_first_relevant: int | None = None
    hit_at_1: float = 0.0
    reciprocal_rank: float = 0.0
    recall_at_k: float = 0.0
    hard_neg_in_k: int = 0
    hard_neg_above_relevant: int = 0
    exclude_leaks: list[str] = field(default_factory=list)
    clean_top1: float = 0.0                # top result is relevant AND not a distractor

    def as_row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "difficulty": self.difficulty,
            "split": self.split,
            "graded": self.graded,
            "hit@1": self.hit_at_1,
            "rr": round(self.reciprocal_rank, 3),
            f"recall@{self.k}": round(self.recall_at_k, 3),
            "rank1st": self.rank_of_first_relevant,
            f"hardneg@{self.k}": self.hard_neg_in_k,
            "hn>rel": self.hard_neg_above_relevant,
            "exclude_leaks": ",".join(self.exclude_leaks),
        }


def score_query(
    *,
    id: str,
    ranked: list[str],
    relevant: list[str],
    hard_negatives: list[str],
    must_exclude: list[str],
    difficulty: str = "",
    split: str = "",
    k: int = 6,
) -> QueryScore:
    rel, hard, excl = set(relevant), set(hard_negatives), set(must_exclude)
    topk = ranked[:k]
    s = QueryScore(
        id=id, difficulty=difficulty, split=split, ranked=ranked,
        relevant=rel, hard_negatives=hard, must_exclude=excl, k=k,
    )
    s.exclude_leaks = [e for e in topk if e in excl]

    # Pure must-exclude query (nothing relevant exists): only graded on leaks.
    s.graded = bool(rel)
    if not s.graded:
        return s

    # First relevant's 1-based rank (None if never returned).
    first = next((i + 1 for i, e in enumerate(ranked) if e in rel), None)
    s.rank_of_first_relevant = first
    s.reciprocal_rank = 1.0 / first if first else 0.0
    s.hit_at_1 = 1.0 if ranked and ranked[0] in rel else 0.0
    s.clean_top1 = 1.0 if ranked and ranked[0] in rel and ranked[0] not in hard else 0.0
    s.recall_at_k = len([e for e in topk if e in rel]) / len(rel)
    s.hard_neg_in_k = len([e for e in topk if e in hard])
    cutoff = first if first else len(ranked) + 1
    s.hard_neg_above_relevant = len(
        [e for i, e in enumerate(ranked) if e in hard and (i + 1) < cutoff]
    )
    return s


@dataclass
class Aggregate:
    n_graded: int
    hit_at_1: float
    mrr: float
    recall_at_k: float
    mean_hard_neg_in_k: float
    mean_hard_neg_above_relevant: float
    clean_top1: float
    exclude_violations: int          # queries leaking a must_exclude in top-k
    misses: int                      # graded queries with no relevant in top-k
    k: int


def aggregate(scores: list[QueryScore]) -> Aggregate:
    graded = [s for s in scores if s.graded]
    n = len(graded) or 1
    k = scores[0].k if scores else 6
    return Aggregate(
        n_graded=len(graded),
        hit_at_1=sum(s.hit_at_1 for s in graded) / n,
        mrr=sum(s.reciprocal_rank for s in graded) / n,
        recall_at_k=sum(s.recall_at_k for s in graded) / n,
        mean_hard_neg_in_k=sum(s.hard_neg_in_k for s in graded) / n,
        mean_hard_neg_above_relevant=sum(s.hard_neg_above_relevant for s in graded) / n,
        clean_top1=sum(s.clean_top1 for s in graded) / n,
        exclude_violations=sum(1 for s in scores if s.exclude_leaks),
        misses=sum(1 for s in graded if s.recall_at_k == 0.0),
        k=k,
    )
