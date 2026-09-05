"""Re-geocode existing city_events through HERE and persist corrected coordinates.

Fixes rows whose stored lat/lng don't match their address (the demo seed was
hand-placed). Uses the same EventsService.geocode_event path the Inngest worker
runs, so it exercises the real enrichment code.

Run from the project root (smart_wroclaw/), with a HERE key in the env or .env:

    CONFIG__HERE__API_KEY=xxxxx poetry run python api/tests/manual/backfill_coords.py
"""

from __future__ import annotations

from api.bootstrap import get_bootstrap
from loguru import logger


def main() -> None:
    bootstrap = get_bootstrap()
    if not bootstrap.here_client.is_configured:
        raise SystemExit(
            "HERE not configured — set CONFIG__HERE__API_KEY (env or .env) first."
        )

    events = bootstrap.events_service.list_events()
    logger.info("backfilling coordinates for {} events", len(events))
    changed = 0
    for event in events:
        before = (event.lat, event.lng)
        updated = bootstrap.events_service.geocode_event(event.id)
        after = (updated.lat, updated.lng)
        if after != before:
            changed += 1
        logger.info(
            "#{} {!r}: {} -> {}",
            event.id,
            event.address or event.location_text,
            before,
            after,
        )
    logger.info("done — {}/{} events moved", changed, len(events))


if __name__ == "__main__":
    main()
