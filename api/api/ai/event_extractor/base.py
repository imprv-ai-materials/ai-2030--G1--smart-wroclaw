"""Contract for the `event_extractor` agent (open text → EventUnderstanding).

The single NL→structured step that fronts both chat tools: the *search* tool
projects the understanding onto the events filter, the *add* tool projects it
onto a create-event draft (see `city_events_bc/models/understanding.py`).
`category` — this agent's original single job — is now just one field of the
richer `EventUnderstanding`, so the curated category dataset/baseline keeps
scoring it.

Degrades gracefully: with no OpenAI key it falls back to a keyword heuristic for
the `category` field (the offline baseline the eval scores), so the agent — and
the DeepEval loop under `eval/` — still runs offline in local dev without
credentials. The output is a PROPOSAL: a human (or a deterministic form for the
missing/ambiguous fields) confirms it.
"""

from abc import ABC, abstractmethod

from api.contexts_boundaries.city_events_bc.models import (
    EventUnderstanding,
    ReportCategory,
)


class AbstractEventExtractor(ABC):
    @abstractmethod
    def extract(
        self,
        text: str,
        user_category: ReportCategory | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> EventUnderstanding:
        """Read `text` (open text a user typed) into a structured proposal.

        `user_category` — when the reporter pre-selected one — is a strong hint
        the agent should usually respect. `history` (prior conversation turns, each
        `{role, content}`) lets the extractor accumulate an event across turns.
        """
        ...
