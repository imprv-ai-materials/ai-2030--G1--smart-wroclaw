"""Contract for the `analytics_agent` — the main agent's counting lane.

Answers "how many …" questions over events, optionally geo-scoped ("… in my
neighbourhood"). Replaces the removed generic Q&A: instead of prose, it returns a
real number (plus a breakdown) and a one-sentence reply. Counting is deterministic;
a model, when present, only phrases the final sentence — never the number.

`scope` is a plain dict from the geo resolver — `{district?, lat?, lng?, radius_m?}`
— so this agent stays decoupled from the geo tool's own types.
"""

from abc import ABC, abstractmethod
from typing import Any

from api.contexts_boundaries.city_events_bc.models import EventUnderstanding
from pydantic import BaseModel, Field


class AnalyticsAnswer(BaseModel):
    count: int
    breakdown: dict[str, int] = Field(default_factory=dict)
    reply: str
    scope: dict[str, Any] | None = None


class AbstractAnalyticsAgent(ABC):
    @abstractmethod
    def answer(
        self,
        understanding: EventUnderstanding,
        *,
        scope: dict[str, Any] | None = None,
    ) -> AnalyticsAnswer:
        """Count events matching `understanding`, narrowed to `scope` (a district or
        a radius around a point), and return the number + a one-line reply."""
        ...
