"""Contract for the `main_agent` — the one agent the whole app is.

It doesn't do the work itself: it *composes* the versioned sub-agents into one turn
— guardrails → extractor → router → one of {search, report, analytics} — leaning on
the shared geo resolver. The chat bounded context depends only on this contract, so
swapping any component (or the composition itself) never touches the domain.

`run_turn` returns a JSON-encodable dict (the same shape the chat REST layer maps
onto `ChatTurnResponse`): always `status`/`reply`, plus intent-specific extras
(`filters`+`results` for search, `draft`+`form`/`ready`+`duplicates`/`created` for
report, `count`+`breakdown` for analytics).
"""

from abc import ABC, abstractmethod
from typing import Any


class AbstractMainAgent(ABC):
    @abstractmethod
    def run_turn(
        self,
        text: str,
        history: list[dict[str, str]] | None = None,
        *,
        fields: dict[str, Any] | None = None,
        action: str | None = None,
        prior_draft: dict[str, Any] | None = None,
        reporter_id: int | None = None,
        reporter_confirmed: bool = False,
    ) -> dict[str, Any]:
        """Run one interactive turn. `history` is prior turns (each with its `intent`,
        so a report continues across turns); `fields`/`action`/`prior_draft` thread the
        add flow; `reporter_id`/`reporter_confirmed` gate the final create on confirm."""
        ...
