"""Contract for the citizen-report triage agent (`city_events_bc`'s AI half).

Given a raw citizen report it proposes a structured `TriageResult` (category,
severity, routing department, summary, draft public response, duplicate flag).
NOTHING here is authoritative — the proposal always goes to a human specialist
for approval before anything reaches the citizen.

The result type (`TriageResult`) and input (`IssueReport`) are *domain* models
owned by `city_events_bc` (they're persisted and shared across the BC), so —
unlike the reference `agents_bc`, whose payloads are agent-private — this `base`
imports them rather than redefining them. What lives here is just the behavioural
contract the domain service depends on.
"""

from abc import ABC, abstractmethod

from api.contexts_boundaries.city_events_bc.models import IssueReport, TriageResult


class AbstractTriageAgent(ABC):
    @abstractmethod
    def triage(self, report: IssueReport) -> TriageResult:
        """Propose a `TriageResult` for `report`.

        Degrades gracefully: with no OpenAI key configured, falls back to a
        keyword heuristic so the review queue still fills in local dev.
        """
        ...
