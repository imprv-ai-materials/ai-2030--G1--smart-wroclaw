"""Contract for the `report_agent` — the main agent's ingestion lane.

Turns a resident's report into a completed city-event draft over one or more turns.
Each turn accumulates: prior draft ⊕ this turn's extraction ⊕ inline-form answers,
then either asks for the missing fields (as a form the frontend renders) or, when
complete, surfaces likely duplicates so a report is never silently dropped.

`ReportTurn` is the result payload (a small value object, kept here per the ai/
convention). The actual create is a service call the orchestrator makes on confirm.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from api.contexts_boundaries.city_events_bc.models import CityEvent, EventUnderstanding


@dataclass(frozen=True)
class ReportTurn:
    """One add turn's outcome. `form` is the inline widget spec for `missing_fields`;
    when `ready`, `duplicates` are likely-existing events to confirm against."""

    draft: dict[str, Any]
    missing_fields: list[str]
    form: list[dict[str, Any]]
    ready: bool
    duplicates: list[CityEvent] = field(default_factory=list)


class AbstractReportAgent(ABC):
    @abstractmethod
    def plan_turn(
        self,
        understanding: EventUnderstanding,
        *,
        prior_draft: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
    ) -> ReportTurn:
        """Plan one ingestion turn. `prior_draft` is the report so far; `fields` are
        this turn's inline-form answers (exact, not recoverable from text)."""
        ...
