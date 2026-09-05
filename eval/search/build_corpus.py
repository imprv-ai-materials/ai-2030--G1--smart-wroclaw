"""Materialise the search eval corpus from the demo events.

The retrieval eval scores the chat *search* tool against a FIXED set of city
events (the "documents"). We snapshot the same demo feed the app seeds
(`api/tests/manual/fake_events.json`) into `data/corpus.jsonl`, giving every row
a stable `ext_id` (`evt-00`…) and a deterministic `created_at` so the current
recency ordering (`ORDER BY created_at DESC`) is reproducible run-to-run.

Regenerate any time the demo feed changes:

    python eval/search/build_corpus.py

Then re-check the query labels in `data/queries.jsonl` still point at the right
`ext_id`s (they are index-stable as long as rows aren't reordered).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "api" / "tests" / "manual" / "fake_events.json"
OUT = Path(__file__).resolve().parent / "data" / "corpus.jsonl"

# A fixed anchor so created_at (and therefore the recency ordering) is stable.
# Row i is stamped one minute after row i-1, so higher index == "newer": the
# current search returns the corpus newest-first, which is exactly what buries an
# older but more relevant event. The eval reproduces that deterministically.
BASE = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def main() -> None:
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for i, e in enumerate(rows):
            stamp = (BASE + timedelta(minutes=i)).isoformat()
            row = {
                "id": i,
                "ext_id": f"evt-{i:02d}",
                "type": e["type"],
                "status": e.get("status") or "ACTIVE",
                "source": e.get("source") or "USER",
                "category": e.get("category"),
                "severity": e.get("severity"),
                "subtype": e.get("subtype"),
                "district": e.get("district"),
                "title": e["title"],
                "description": e.get("description") or "",
                "location_text": e.get("location_text"),
                "address": e.get("address"),
                "lat": e.get("lat"),
                "lng": e.get("lng"),
                "confirmations": e.get("confirmations") or 0,
                "verified": bool(e.get("verified")),
                "details": e.get("details") or {},
                # Evergreen: no expiry, so nothing falls off by time — the eval
                # isolates ranking/matching, not the TTL sweep.
                "expires_at": None,
                "reporter_id": e.get("reporter_id") or 1,
                "created_at": stamp,
                "updated_at": stamp,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} events → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
