"""Contract for the `router` agent — picks the task once guardrails let a message in.

The main agent runs exactly one lane per turn; this decides which. Input is the
message plus the extractor's structured reading (and the running conversation, so
a report-in-progress keeps flowing); output is one `Intent` with a confidence and
a one-line rationale. Degrades gracefully to a keyword heuristic offline.
"""

from abc import ABC, abstractmethod
from enum import StrEnum

from api.contexts_boundaries.city_events_bc.models import EventUnderstanding
from pydantic import BaseModel


class Intent(StrEnum):
    SEARCH = "search"  # find matching events (map + cards)
    REPORT = "report"  # file / ingest a new city event
    ANALYTICS = "analytics"  # count / aggregate, geo-scoped ("ile … w mojej okolicy")


class RouteDecision(BaseModel):
    intent: Intent
    confidence: float = 0.0
    rationale: str = ""


class AbstractRouterAgent(ABC):
    @abstractmethod
    def route(
        self,
        text: str,
        understanding: EventUnderstanding,
        history: list[dict[str, str]] | None = None,
    ) -> RouteDecision:
        """Classify the turn's intent. `understanding` is the extractor's reading;
        `history` lets the router continue an add flow already in progress."""
        ...
