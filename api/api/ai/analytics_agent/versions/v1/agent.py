"""analytics_agent · v1 — deterministic count over the events repo, geo-scoped.

Projects the reading onto filters, fetches ACTIVE events, narrows to the geo scope
(a district name, or a radius around a point via haversine), counts, and buckets by
type. The number is always computed in code; the reply is a Polish template — unless
an OpenAI key is present, in which case the model only *phrases* the same number.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from api.adapters.llm import OpenAIClient
from api.ai.analytics_agent.base import AbstractAnalyticsAgent, AnalyticsAnswer
from api.ai.analytics_agent.versions.v1.prompts import SYSTEM_PROMPT
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


def _plural_events(n: int) -> str:
    if n == 1:
        return "zdarzenie"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "zdarzenia"
    return "zdarzeń"


class AnalyticsAgent(AbstractAnalyticsAgent):
    def __init__(
        self,
        events_repository: AbstractEventsRepository,
        openai_client: OpenAIClient | None = None,
        model: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._events = events_repository
        self._client = openai_client
        self._model = model
        self._system_prompt = system_prompt

    def answer(
        self,
        understanding: EventUnderstanding,
        *,
        scope: dict[str, Any] | None = None,
    ) -> AnalyticsAnswer:
        filters = to_search_filters(understanding)
        events = self._events.list(
            status=EventStatus.ACTIVE,
            type_=filters["type_"],
            category=filters["category"],
            district=filters["district"],
        )
        now = _utcnow()
        events = [e for e in events if e.expires_at is None or e.expires_at > now]
        events = self._apply_scope(events, scope)

        count = len(events)
        breakdown: dict[str, int] = {}
        for e in events:
            key = e.type.value if e.type else "OTHER"
            breakdown[key] = breakdown.get(key, 0) + 1

        # Phrase the "where" from the NORMALISED district (filters), so a city-wide
        # query never reads back as "w dzielnicy Wrocław" (chat 3).
        reply = self._phrase(count, filters["district"], scope)
        return AnalyticsAnswer(count=count, breakdown=breakdown, reply=reply, scope=scope)

    @staticmethod
    def _apply_scope(events: list[CityEvent], scope: dict[str, Any] | None) -> list[CityEvent]:
        if not scope:
            return events
        district = scope.get("district")
        if district:
            needle = str(district).lower()
            events = [e for e in events if e.district and needle in e.district.lower()]
        lat, lng, radius = scope.get("lat"), scope.get("lng"), scope.get("radius_m")
        if lat is not None and lng is not None and radius:
            events = [
                e
                for e in events
                if e.lat is not None and e.lng is not None and _haversine_m(lat, lng, e.lat, e.lng) <= radius
            ]
        return events

    def _phrase(self, count: int, district: str | None, scope: dict[str, Any] | None) -> str:
        where = ""
        if scope and scope.get("district"):
            where = f" w dzielnicy {scope['district']}"
        elif scope and scope.get("radius_m"):
            where = f" w promieniu {round(scope['radius_m'] / 1000, 1)} km"
        elif district:
            where = f" w dzielnicy {district}"
        templated = (
            f"Nie znalazłem pasujących zdarzeń{where}."
            if count == 0
            else f"Znalazłem {count} {_plural_events(count)}{where}."
        )
        if self._client is None or not self._client.is_configured:
            return templated
        user = f"Liczba: {count}. Zakres: {where or 'całe miasto'}. Ujmij to w jedno zdanie."
        try:
            return self._client.complete_text(system=self._system_prompt, user=user, model=self._model)
        except Exception:
            return templated  # phrasing is best-effort; the number is what matters
