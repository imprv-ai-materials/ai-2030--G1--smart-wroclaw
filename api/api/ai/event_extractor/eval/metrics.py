"""Metrics for the category eval — deterministic, no LLM judge.

Primary-category classification is a closed set, so we score it with an EXACT
match rather than an LLM-as-judge: free, reproducible, and impossible for the
agent (or a future optimiser) to game by wording. `PrimaryCategoryMatchMetric`
plugs into DeepEval's `evaluate()` / `assert_test()`; the plain helpers below
(per-class P/R/F1, secondary set-F1, bootstrap CI) power the richer report in
run_deepeval.py and encode the anti-overfitting rigour (error bars, not just a
point estimate).
"""

from __future__ import annotations

import random
from collections import defaultdict

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


class PrimaryCategoryMatchMetric(BaseMetric):
    """1.0 when the predicted primary category exactly equals the expected one.

    Reads `test_case.expected_output` (gold label) and `test_case.actual_output`
    (agent's prediction) — both plain category strings like "ROADS".
    """

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold
        # BaseMetric bookkeeping DeepEval's runner expects to find set.
        self.async_mode = False
        self.strict_mode = False
        self.verbose_mode = False
        self.include_reason = True
        self.error: str | None = None
        self.evaluation_cost = 0
        self.score = 0.0
        self.success = False
        self.reason = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        expected = (test_case.expected_output or "").strip().upper()
        actual = (test_case.actual_output or "").strip().upper()
        self.score = 1.0 if expected and actual == expected else 0.0
        self.success = self.score >= self.threshold
        self.reason = "trafiona" if self.success else f"oczekiwano {expected}, otrzymano {actual or '∅'}"
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self):
        return "Primary Category Match"


# --------------------------- plain scoring helpers ---------------------------


def secondary_set_f1(expected: list[str], actual: list[str]) -> float:
    """F1 over the *set* of secondary categories. Empty-vs-empty counts as 1.0
    (correctly predicting 'no extra categories')."""
    e, a = set(expected), set(actual)
    if not e and not a:
        return 1.0
    if not e or not a:
        return 0.0
    tp = len(e & a)
    if tp == 0:
        return 0.0
    precision = tp / len(a)
    recall = tp / len(e)
    return 2 * precision * recall / (precision + recall)


def per_class_prf(expected: list[str], predicted: list[str], labels: list[str]) -> dict[str, dict[str, float]]:
    """Per-class precision / recall / F1 / support for the primary label."""
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = defaultdict(int)
    for e, p in zip(expected, predicted):
        support[e] += 1
        if e == p:
            tp[e] += 1
        else:
            fp[p] += 1
            fn[e] += 1
    out: dict[str, dict[str, float]] = {}
    for c in labels:
        prec = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        rec = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        out[c] = {"precision": prec, "recall": rec, "f1": f1, "support": support[c]}
    return out


def macro_f1(per_class: dict[str, dict[str, float]]) -> float:
    present = [m["f1"] for m in per_class.values() if m["support"] > 0]
    return sum(present) / len(present) if present else 0.0


def bootstrap_ci(
    scores: list[float], n_resamples: int = 10000, alpha: float = 0.05, seed: int = 13
) -> tuple[float, float, float]:
    """Percentile bootstrap 95% CI for the mean of per-item scores.

    Deterministic (fixed seed) so the reported interval is stable across runs.
    Returns (mean, low, high).
    """
    n = len(scores)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(scores) / n
    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        s = 0.0
        for _ in range(n):
            s += scores[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * n_resamples)]
    hi = means[int((1 - alpha / 2) * n_resamples) - 1]
    return mean, lo, hi
