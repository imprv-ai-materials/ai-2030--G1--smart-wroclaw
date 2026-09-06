"""Contract for the `guardrails` agent — the main agent's front door.

Every resident message hits this first. Two layers behind one call:
  • technical — non-empty, length-bounded, no obvious injection (deterministic);
  • topical (LLM) — is this actually about Wrocław city events? A pancake recipe,
    a poem, general chit-chat → refused politely before any tool runs.

The verdict is a small value object (below), not a domain model: it never leaves
the agent boundary except as the accept/refuse decision the main agent acts on.
Degrades gracefully — with no OpenAI key the topical layer falls back to a keyword
heuristic so the stack (and the eval) still runs offline.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class GuardrailVerdict(BaseModel):
    """Accept/refuse decision for one message.

    `reason` is a stable machine code the orchestrator branches on; `rationale`
    is an optional one-line human explanation (shown to the resident on refuse).
    """

    allow: bool
    # ok | empty | too_long | blocked_content | off_topic
    reason: str
    rationale: str = ""


class AbstractGuardrailAgent(ABC):
    @abstractmethod
    def check(self, text: str, history: list[dict[str, str]] | None = None) -> GuardrailVerdict:
        """Decide whether `text` may proceed to routing. `history` (prior turns)
        lets a follow-up like "tak, potwierdzam" pass inside an on-topic flow."""
        ...
