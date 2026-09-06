"""Contract for the `search_agent` — the main agent's retrieval lane.

Turns the extractor's structured reading into a *ranked* list of events for the
map + cards. Returning a plain `list[CityEvent]` (a domain model) means there's no
payload type to define here — the value is the ORDER. The concrete version depends
only on an events repository, so the whole thing runs offline against the in-memory
eval corpus; ranking quality is scored by the `main_agent` IR loop.
"""

from abc import ABC, abstractmethod

from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventStatus,
    EventUnderstanding,
)


class AbstractSearchAgent(ABC):
    @abstractmethod
    def search(
        self,
        understanding: EventUnderstanding,
        *,
        status: EventStatus | None = None,
        k: int | None = None,
    ) -> list[CityEvent]:
        """Return events matching `understanding`, best first. `status` optionally
        constrains the feed (e.g. only ACTIVE); `k` caps the window (chat shows 6)."""
        ...
