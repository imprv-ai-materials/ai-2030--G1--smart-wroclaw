"""router · v1 — keyword heuristic offline, structured LLM classification with a key.

The offline heuristic ports the orchestrator's original `_route`, extended with an
`analytics` lane (count/aggregate tells). Precedence is deliberate: an in-progress
report continues; explicit analytics beats explicit search; a bare structured
reading (`understanding.type`) leans search; the safe default is search (showing
events is cheaper to recover from than mis-filing a report).
"""

from api.adapters.llm import OpenAIClient
from api.ai.router_agent.base import AbstractRouterAgent, Intent, RouteDecision
from api.ai.router_agent.versions.v1.prompts import SYSTEM_PROMPT
from api.contexts_boundaries.city_events_bc.models import EventUnderstanding

_SEARCH_HINTS = (
    "szukaj",
    "znajd",
    "pokaż",
    "pokaz",
    "czy są",
    "czy sa",
    "lista",
    "filtr",
    "wyszuka",
    "co się dzieje",
    "co sie dzieje",
)
_REPORT_HINTS = (
    "zgłoś",
    "zglos",
    "zgłas",
    "zglas",
    "zgłaszam",
    "zglaszam",
    "dodaj",
    "zaginął",
    "zaginal",
    "znalazłem",
    "znalazlem",
    "chcę zgłosić",
    "chce zglosic",
)
_ANALYTICS_HINTS = (
    "ile",
    "ilu",
    "liczba",
    "liczb",
    "statyst",
    "średnio",
    "srednio",
    "łącznie",
    "lacznie",
    "w sumie",
    "jak wiele",
    "how many",
)


class RouterAgent(AbstractRouterAgent):
    def __init__(
        self,
        openai_client: OpenAIClient,
        model: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._system_prompt = system_prompt

    def route(
        self,
        text: str,
        understanding: EventUnderstanding,
        history: list[dict[str, str]] | None = None,
    ) -> RouteDecision:
        if not self._client.is_configured:
            return self._offline_route(text, understanding, history)

        prev = self._prev_intent(history)
        user = (
            f"Wiadomość: {text}\n"
            f"Odczyt (typ): {understanding.type.value if understanding.type else 'brak'}\n"
            f"Poprzednia intencja: {prev or 'brak'}"
        )
        return self._client.complete_structured(
            system=self._system_prompt, user=user, schema=RouteDecision, model=self._model
        )

    @staticmethod
    def _prev_intent(history: list[dict[str, str]] | None) -> str | None:
        for item in reversed(history or []):
            if item.get("role") == "ASSISTANT":
                return item.get("intent")
        return None

    def _offline_route(self, text: str, u: EventUnderstanding, history: list[dict[str, str]] | None) -> RouteDecision:
        low = (text or "").lower()
        if any(h in low for h in _ANALYTICS_HINTS):
            return RouteDecision(intent=Intent.ANALYTICS, confidence=0.5, rationale="pytanie o liczbę (heurystyka)")
        if any(h in low for h in _SEARCH_HINTS):
            return RouteDecision(intent=Intent.SEARCH, confidence=0.5, rationale="prośba o wyszukanie (heurystyka)")
        if self._prev_intent(history) == "report":
            return RouteDecision(intent=Intent.REPORT, confidence=0.5, rationale="kontynuacja zgłoszenia (heurystyka)")
        if any(h in low for h in _REPORT_HINTS) or (u.title and (u.location_text or u.address)):
            return RouteDecision(intent=Intent.REPORT, confidence=0.5, rationale="zamiar zgłoszenia (heurystyka)")
        if u.type is not None:
            return RouteDecision(
                intent=Intent.SEARCH, confidence=0.35, rationale="odczytany typ → wyszukiwanie (heurystyka)"
            )
        return RouteDecision(intent=Intent.SEARCH, confidence=0.2, rationale="domyślnie wyszukiwanie (heurystyka)")
