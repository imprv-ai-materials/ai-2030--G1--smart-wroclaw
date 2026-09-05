"""Contract for the city-maintenance Q&A agent (the chat "answer" intent).

The agent answers user questions about municipal services in Wrocław — waste
collection, water outages, MPK transport, road works, lighting, greenery. The
contract here is deliberately tiny — one `answer()` turn — so the chat
orchestrator (which calls it for the "answer" intent) depends only on this ABC,
never on a concrete version. The live implementation is picked per deployment
from `versions/current.yaml` and lives under `versions/vN/agent.py`.

This agent returns a plain `str`, so there's no payload model to define — just
the behavioural contract.
"""

from abc import ABC, abstractmethod


class AbstractAssistantAgent(ABC):
    @abstractmethod
    def answer(self, question: str, history: list[dict[str, str]] | None = None) -> str:
        """Answer one user question, optionally given prior turns as `history`.

        Degrades gracefully: with no OpenAI key configured, returns a templated
        offline fallback so the stack stays runnable in local dev.
        """
        ...
