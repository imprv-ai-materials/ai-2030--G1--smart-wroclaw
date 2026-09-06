"""An importable in-memory events repository for the eval harness.

Lets the agents that read events (search / report / analytics) run their real code
path offline against a small corpus, with no Postgres. `.list()` mirrors the SQL
semantics of the production `EventsRepository` (exact match on status/type/category/
severity, substring on district, newest-first). `from_corpus` is tolerant: it fills
the NOT-NULL columns a minimal seed corpus tends to omit (`reporter_id`,
`updated_at`, `source`) so a hand-authored `corpus.jsonl` loads without ceremony.
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
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return cls([CityEvent.from_dict(_fill_defaults(r)) for r in rows])

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
        out = sorted(out, key=lambda e: e.created_at, reverse=True)
        return out[:limit]

    def get(self, event_id: int) -> CityEvent | None:
        return next((e for e in self._events if e.id == event_id), None)

    # -- writes: not part of a read-only retrieval eval -----------------------
    def create(self, values: dict[str, Any]) -> CityEvent:  # pragma: no cover
        raise NotImplementedError("read-only eval repository")

    def create_many(self, rows: list[dict[str, Any]]) -> list[CityEvent]:  # pragma: no cover
        raise NotImplementedError("read-only eval repository")

    def update(self, event_id: int, values: dict[str, Any]) -> CityEvent | None:  # pragma: no cover
        raise NotImplementedError("read-only eval repository")


def _fill_defaults(row: dict[str, Any]) -> dict[str, Any]:
    """Fill the columns `CityEvent.from_dict` requires that a minimal seed omits."""
    out = dict(row)
    out.setdefault("reporter_id", 1)
    out.setdefault("updated_at", out.get("created_at"))
    out.setdefault("source", "CITY")
    return out
