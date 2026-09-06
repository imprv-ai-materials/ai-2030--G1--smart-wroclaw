"""guardrails · v1 — technical checks + a topical gate (LLM, offline heuristic).

The technical layer is always deterministic (empty / too long / injection). The
topical layer asks the model "is this about city events?"; with no key it falls
back to keyword tells and, when neither on- nor off-topic words match, FAILS OPEN
(allows) — offline we would rather let a real report through than block it. The
keyword tables are the offline "model" the eval scores; keep them diff-friendly.
"""

from api.adapters.llm import OpenAIClient
from api.ai.guardrails_agent.base import AbstractGuardrailAgent, GuardrailVerdict
from api.ai.guardrails_agent.versions.v1.prompts import SYSTEM_PROMPT

_MAX_LEN = 2000
_INJECTION = ("<script", "javascript:", "onerror=")

# Clearly-not-city-events tells (offline refuse).
_OFF_TOPIC = (
    "przepis",
    "naleśnik",
    "nalesnik",
    "ciasto",
    "wiersz",
    "opowiadanie",
    "żart",
    "zart",
    "przetłumacz",
    "przetlumacz",
    "kod w python",
    "napisz program",
    "stolica",
    "pogoda",
    "horoskop",
    "randk",
)
# City-event vocabulary (offline allow). Kept broad — search/report/analytics all.
_ON_TOPIC = (
    "zgłoś",
    "zglos",
    "zgłasz",
    "zglasz",
    "awaria",
    "awari",
    "usterk",
    "zaginął",
    "zaginal",
    "zaginęł",
    "znalazł",
    "zdarzeni",
    "zgłoszeni",
    "szukam",
    "szukaj",
    "pokaż",
    "pokaz",
    "znajdź",
    "znajdz",
    "ile",
    "ilu",
    "liczba",
    "woda",
    "wod",
    "droga",
    "drog",
    "dziur",
    "śmiec",
    "smiec",
    "odpad",
    "latarni",
    "oświetl",
    "oswietl",
    "tramwaj",
    "autobus",
    "mpk",
    "park",
    "drzew",
    "zieleń",
    "zielen",
    "dzielnic",
    "krzyk",
    "nadodrz",
    "psi",
    "pies",
    "kot",
    "zwierz",
    "promocj",
    "wydarzeni",
    "utrudnieni",
    "roboty",
    "zagrożeni",
    "zagrozeni",
    "potwierdz",
    "tak",
)


class GuardrailAgent(AbstractGuardrailAgent):
    def __init__(
        self,
        openai_client: OpenAIClient,
        model: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._system_prompt = system_prompt

    def check(self, text: str, history: list[dict[str, str]] | None = None) -> GuardrailVerdict:
        t = (text or "").strip()
        if not t:
            return GuardrailVerdict(allow=False, reason="empty", rationale="pusta wiadomość")
        if len(t) > _MAX_LEN:
            return GuardrailVerdict(allow=False, reason="too_long", rationale="wiadomość zbyt długa")
        low = t.lower()
        if any(bad in low for bad in _INJECTION):
            return GuardrailVerdict(allow=False, reason="blocked_content", rationale="niedozwolona treść")

        if not self._client.is_configured:
            return self._offline_topical(low)

        return self._client.complete_structured(
            system=self._system_prompt,
            user=t,
            schema=GuardrailVerdict,
            model=self._model,
        )

    @staticmethod
    def _offline_topical(low: str) -> GuardrailVerdict:
        if any(k in low for k in _ON_TOPIC):
            return GuardrailVerdict(allow=True, reason="ok", rationale="temat miejski (heurystyka offline)")
        if any(k in low for k in _OFF_TOPIC):
            return GuardrailVerdict(
                allow=False, reason="off_topic", rationale="poza tematem zdarzeń miejskich (heurystyka offline)"
            )
        # Fail open: don't block an unrecognised message offline — a live model decides.
        return GuardrailVerdict(allow=True, reason="ok", rationale="brak sygnału off-topic (heurystyka offline)")
