"""An in-memory events repository over the eval corpus.

Lets the eval drive the REAL search code path (`EventsService.list_events`
→ recency ordering + in-process expiry/`q` filter) offline, with no Postgres.
`.list()` mirrors the SQL semantics of the production `EventsRepository`:
exact match on status/type/category/severity, `ILIKE '%d%'` on district, and
`ORDER BY created_at DESC`. Writes are unsupported — the eval is read-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from api.contexts_boundaries.city_events_bc.repositories import AbstractEventsRepository


class InMemoryEventsRepository(AbstractEventsRepository):
    def __init__(self, events: list[CityEvent]) -> None:
        self._events = list(events)

    @classmethod
    def from_corpus(cls, path: Path) -> "InMemoryEventsRepository":
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls([CityEvent.from_dict(r) for r in rows])

    def list(
        self,
        status: EventStatus | None = None,
        type_: EventType | None = None,
        types: list[EventType] | None = None,
        category: ReportCategory | None = None,
        district: str | None = None,
        severity: Severity | None = None,
        limit: int = 500,
    ) -> list[CityEvent]:
        out = self._events
        if status is not None:
            out = [e for e in out if e.status == status]
        if types:
            out = [e for e in out if e.type in types]
        elif type_ is not None:
            out = [e for e in out if e.type == type_]
        if category is not None:
            out = [e for e in out if e.category == category]
        if severity is not None:
            out = [e for e in out if e.severity == severity]
        if district:
            needle = district.lower()
            out = [e for e in out if e.district and needle in e.district.lower()]
        # Mirror `ORDER BY created_at DESC` — the crux of the "not at the top"
        # complaint: newest-first, no relevance signal.
        out = sorted(out, key=lambda e: e.created_at, reverse=True)
        return out[:limit]

    # -- writes: not part of a read-only retrieval eval -----------------------
    def create(self, values: dict[str, Any]) -> CityEvent:  # pragma: no cover
        raise NotImplementedError("read-only eval repository")

    def create_many(self, rows: list[dict[str, Any]]) -> list[CityEvent]:  # pragma: no cover
        raise NotImplementedError("read-only eval repository")

    def get(self, event_id: int) -> CityEvent | None:
        return next((e for e in self._events if e.id == event_id), None)

    def update(self, event_id: int, values: dict[str, Any]) -> CityEvent | None:  # pragma: no cover
        raise NotImplementedError("read-only eval repository")
