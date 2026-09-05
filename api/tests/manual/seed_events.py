"""Seed the `city_events` table with demo events for the user map.

Loads the sibling `fake_events.json` and ingests it through the EventsService
(same validation/normalisation the REST ingest uses). Idempotency is NOT
attempted — re-running appends another copy, so it's a demo/dev convenience.

Run from the project root (smart_wroclaw/) — usually via the pypyr shortcut:

    pypyr seed_events
    # or against a JSON file of your choosing:
    pypyr seed_events dataset=path/to/events.json

which wraps the direct invocation:

    poetry run python api/tests/manual/seed_events.py [path/to/events.json]

Requires a reachable Postgres + applied migrations (`pypyr migrate`). This
touches no network — it only writes rows (coordinates come straight from the
JSON; run `pypyr seed_events geocode=1` to re-geocode them through HERE).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from api.bootstrap import get_bootstrap
from loguru import logger

DEFAULT_DATASET = Path(__file__).resolve().parent / "fake_events.json"


def main() -> None:
    dataset = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    if not dataset.exists():
        raise SystemExit(f"dataset not found: {dataset}")

    raw = json.loads(dataset.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("dataset must be a JSON array of event objects")

    logger.info("seeding {} events from {}", len(raw), dataset)
    created = get_bootstrap().events_service.ingest(raw)
    logger.info("done — inserted {} city_events rows", len(created))
    for ev in created:
        logger.info("  #{} [{}/{}] {}", ev.id, ev.type.value, ev.status.value, ev.title)


if __name__ == "__main__":
    main()
