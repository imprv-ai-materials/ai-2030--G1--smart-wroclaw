"""assistant_agent · v1 — static-prompt city Q&A (offline-safe).

The "knowledge base" is a static briefing baked into the system prompt; a later
version would ground answers in real municipal data (RAG over the city's
open-data portal, GTFS, ticketing). Falls back to a templated answer when no
OpenAI key is configured, so the whole stack runs offline in local dev.
"""

from api.adapters.llm import OpenAIClient
from api.ai.assistant_agent.base import AbstractAssistantAgent
from api.ai.assistant_agent.versions.v1.prompts import SYSTEM_PROMPT


class AssistantAgent(AbstractAssistantAgent):
    def __init__(
        self,
        openai_client: OpenAIClient,
        model: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._system_prompt = system_prompt

    def answer(self, question: str, history: list[dict[str, str]] | None = None) -> str:
        if not self._client.is_configured:
            return self._offline_answer(question)

        history = history or []
        # Fold prior turns into the user prompt (keeps the client surface tiny).
        transcript = "\n".join(f"{h['role']}: {h['content']}" for h in history[-8:])
        user = question if not transcript else f"Dotychczasowa rozmowa:\n{transcript}\n\nNowe pytanie:\n{question}"
        return self._client.complete_text(system=self._system_prompt, user=user, model=self._model)

    def _offline_answer(self, question: str) -> str:
        return (
            "⚠️ Tryb offline (brak skonfigurowanego klucza OpenAI).\n\n"
            f"Otrzymałem pytanie: „{question.strip()}”.\n\n"
            "Po podłączeniu modelu udzielę tu odpowiedzi o utrzymaniu miasta "
            "(odpady, woda, MPK, drogi, oświetlenie, zieleń). "
            "Jeśli chcesz zgłosić konkretny problem do interwencji, skorzystaj z "
            "zakładki „Zgłoś problem” — Twoje zgłoszenie trafi do specjalisty miejskiego."
        )
