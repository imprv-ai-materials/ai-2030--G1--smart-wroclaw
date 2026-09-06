"""search_agent · v1 — deterministic baseline ranking over an events repository.

This isolates today's search behaviour behind an agent boundary so it owns its own
eval and becomes the single place the ranking fix lands. It reproduces the baseline
the `main_agent` IR loop scores: project the reading onto filters, fetch from the
repo, drop expired, apply the free-text `q` substring, order newest first.

A `scope` from the geo_resolver narrows it further — a district name backfills the
facet, and a `{lat,lng,radius_m}` point keeps only events within that radius (the
"events nearby" case, via haversine).

The two known weaknesses live here ON PURPOSE (the eval proves them; a v2 fixes them):
  • `to_search_filters` discards `q` once any facet is set → pure recency ranking;
  • no status filter by default → RESOLVED/EXPIRED events can leak in.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

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


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000  # earth radius, metres
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class SearchAgent(AbstractSearchAgent):
    def __init__(self, events_repository: AbstractEventsRepository) -> None:
        self._events = events_repository

    def search(
        self,
        understanding: EventUnderstanding,
        *,
        scope: dict[str, Any] | None = None,
        status: EventStatus | None = None,
        k: int | None = None,
    ) -> list[CityEvent]:
        filters = to_search_filters(understanding)
        # A resolved district backfills the facet when the reading didn't carry one
        # (e.g. the extractor missed "na Krzykach" but the geo_resolver caught it).
        district = filters["district"] or (scope or {}).get("district")
        events = self._events.list(
            status=status,
            type_=filters["type_"],
            category=filters["category"],
            district=district,
        )
        # Expired events stay in the DB but fall off the feed (None = never expires).
        now = _utcnow()
        events = [e for e in events if e.expires_at is None or e.expires_at > now]
        # Free-text `q` is a substring pass — only present when nothing structured
        # matched (see to_search_filters). TODO(v2): keep it as a ranking signal.
        needle = (filters.get("q") or "").strip().lower()
        if needle:
            events = [e for e in events if needle in self._haystack(e)]
        # "Events nearby": keep only those within the resolved radius of the point.
        events = self._within_scope(events, scope)
        # TODO(v2): replace recency with a relevance score (facet + token overlap).
        events = sorted(events, key=lambda e: e.created_at, reverse=True)
        return events[:k] if k else events

    @staticmethod
    def _within_scope(events: list[CityEvent], scope: dict[str, Any] | None) -> list[CityEvent]:
        if not scope:
            return events
        lat, lng, radius = scope.get("lat"), scope.get("lng"), scope.get("radius_m")
        if lat is None or lng is None or not radius:
            return events  # no point/radius → nothing to filter (district already applied)
        return [
            e
            for e in events
            if e.lat is not None and e.lng is not None and _haversine_m(lat, lng, e.lat, e.lng) <= radius
        ]

    @staticmethod
    def _haystack(event: CityEvent) -> str:
        parts = [event.title, event.description, event.location_text, event.address]
        return " ".join(p for p in parts if p).lower()
