"""search_agent · v1 — deterministic baseline ranking over an events repository.

This isolates today's search behaviour behind an agent boundary so it owns its own
eval and becomes the single place the ranking fix lands. It reproduces the baseline
the `main_agent` IR loop scores: project the reading onto filters, fetch from the
repo, drop expired, apply the free-text `q` substring, order newest first.

The two known weaknesses live here ON PURPOSE (the eval proves them; a v2 fixes them):
  • `to_search_filters` discards `q` once any facet is set → pure recency ranking;
  • no status filter by default → RESOLVED/EXPIRED events can leak in.
"""

from __future__ import annotations

from datetime import datetime, timezone

from api.ai.search_agent.base import AbstractSearchAgent
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventStatus,
    EventUnderstanding,
    to_search_filters,
)
from api.contexts_boundaries.city_events_bc.repositories import AbstractEventsRepository


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class SearchAgent(AbstractSearchAgent):
    def __init__(self, events_repository: AbstractEventsRepository) -> None:
        self._events = events_repository

    def search(
        self,
        understanding: EventUnderstanding,
        *,
        status: EventStatus | None = None,
        k: int | None = None,
    ) -> list[CityEvent]:
        filters = to_search_filters(understanding)
        events = self._events.list(
            status=status,
            type_=filters["type_"],
            category=filters["category"],
            district=filters["district"],
        )
        # Expired events stay in the DB but fall off the feed (None = never expires).
        now = _utcnow()
        events = [e for e in events if e.expires_at is None or e.expires_at > now]
        # Free-text `q` is a substring pass — only present when nothing structured
        # matched (see to_search_filters). TODO(v2): keep it as a ranking signal.
        needle = (filters.get("q") or "").strip().lower()
        if needle:
            events = [e for e in events if needle in self._haystack(e)]
        # TODO(v2): replace recency with a relevance score (facet + token overlap).
        events = sorted(events, key=lambda e: e.created_at, reverse=True)
        return events[:k] if k else events

    @staticmethod
    def _haystack(event: CityEvent) -> str:
        parts = [event.title, event.description, event.location_text, event.address]
        return " ".join(p for p in parts if p).lower()
