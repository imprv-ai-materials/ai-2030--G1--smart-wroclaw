"""CI regression gate for category_agent, scored with DeepEval.

    deepeval test run eval/category_agent/test_category_agent_deepeval.py
    # or plain:  pytest eval/category_agent/test_category_agent_deepeval.py

Two gates, both on the DEV split (the held-out `test` split is deliberately NOT
gated here — reserve it for periodic release checks, not per-PR, to avoid
overfitting to it):

  1. Aggregate accuracy ≥ DEV_ACCURACY_GATE  — the real regression guard. A
     per-case assert would be too strict for a classifier (an 85% baseline would
     show red), so we gate the aggregate. RATCHET THIS UP as the agent improves;
     never lower it — that's the whole point of a regression gate.
  2. A handful of must-never-break easy cases, asserted per-case via DeepEval's
     assert_test, so an obvious breakage fails loudly with the offending input.

Runs on the offline baseline by default, so CI needs no API key.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "NO")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
DATA_DIR = Path(__file__).resolve().parent / "data"

from api.adapters.llm import OpenAIClient  # noqa: E402
from api.ai import load_current  # noqa: E402
from deepeval import assert_test  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402
from metrics import PrimaryCategoryMatchMetric  # noqa: E402

#: Current offline-baseline dev accuracy is ~0.855; gate a little below and
#: raise it every time the agent genuinely improves.
DEV_ACCURACY_GATE = 0.80

#: Unambiguous cases that must never regress, whatever else changes.
SMOKE_CASES = [
    ("Z hydrantu przy ul. Legnickiej tryska woda i zalewa chodnik.", "WATER"),
    ("Głęboka dziura w jezdni na ul. Krakowskiej, można urwać koło.", "ROADS"),
    ("Kontener na odpady zmieszane nie był opróżniony w tym tygodniu.", "WASTE"),
    ("Nie świeci latarnia przy przejściu dla pieszych, wieczorem jest ciemno.", "LIGHTING"),
    ("Rozbita wiata przystankowa MPK na przystanku Rynek.", "PUBLIC_TRANSPORT"),
]


def _agent():
    return load_current("event_extractor").agent_class(OpenAIClient(api_key=None))


def _predict(agent, text: str) -> str:
    cat = agent.extract(text).category
    return cat.value if cat else "OTHER"


def _dev_rows() -> list[dict]:
    path = DATA_DIR / "dev.jsonl"
    if not path.is_file():
        pytest.skip("dataset not generated — run generate_dataset.py")
    return [json.loads(li) for li in path.read_text(encoding="utf-8").splitlines() if li.strip()]


def test_dev_primary_accuracy_gate() -> None:
    agent = _agent()
    rows = _dev_rows()
    metric = PrimaryCategoryMatchMetric()
    hits = 0
    for r in rows:
        pred = _predict(agent, r["text"])
        case = LLMTestCase(input=r["text"], actual_output=pred, expected_output=r["primary_category"])
        hits += metric.measure(case)
    accuracy = hits / len(rows)
    assert (
        accuracy >= DEV_ACCURACY_GATE
    ), f"dev primary accuracy {accuracy:.3f} < gate {DEV_ACCURACY_GATE:.3f} — regression."


@pytest.mark.parametrize("text,expected", SMOKE_CASES, ids=[e for _, e in SMOKE_CASES])
def test_smoke_case(text: str, expected: str) -> None:
    agent = _agent()
    pred = _predict(agent, text)
    case = LLMTestCase(input=text, actual_output=pred, expected_output=expected)
    assert_test(case, [PrimaryCategoryMatchMetric()])
