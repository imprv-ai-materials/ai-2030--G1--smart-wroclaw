"""Append-only history of eval runs — one JSONL ledger per agent.

Every scored run appends a line to `ai/<agent>/eval_runs.jsonl` (committed, so the
score history for each version travels with the repo). A line is a flat record:
timestamp · version · dataset · split · sample% · the headline metrics. This is
what lets you answer "did v2 actually beat v1 on this dataset?" over time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ledger_path(ai_dir: Path, agent: str) -> Path:
    return ai_dir / agent / "eval_runs.jsonl"


def append_run(ai_dir: Path, agent: str, record: dict[str, Any]) -> Path:
    path = ledger_path(ai_dir, agent)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def load_runs(ai_dir: Path, agent: str) -> list[dict[str, Any]]:
    path = ledger_path(ai_dir, agent)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
