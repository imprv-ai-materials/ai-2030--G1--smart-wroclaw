"""guardrails · v2 (from v1) — history-aware topical gate on a cheaper model.

Three deliberate changes over v1, kept as a thin diff (subclass of v1):
  • MODEL is HARD-LOCKED to `gpt-5.4-mini` INSIDE this version — the model is part
    of a version's identity, full stop. Any `model` argument from bootstrap /
    current.yaml is ignored; promotion (or rollback) carries the model with it.
  • the LLM call now receives the conversation `history`, so a context-only
    follow-up ("a jednak zielony", "nie, to była żółta") is judged on-topic inside
    a running flow. v1 accepted `history` but silently dropped it before the model.
  • the offline fallback checks STRONG off-topic tells (injection, homework, bare
    arithmetic, code) BEFORE the soft on-topic words ("ile", "tak"), so weak
    keyword bait no longer flips a clearly off-topic message to allow.
"""

from api.adapters.llm import OpenAIClient
from api.ai.guardrails_agent.base import GuardrailVerdict
from api.ai.guardrails_agent.versions.v1.agent import GuardrailAgent as GuardrailAgentV1
from api.ai.guardrails_agent.versions.v2.prompts import SYSTEM_PROMPT

#: The model IS this version — hard-locked here, never read from config/current.yaml.
MODEL = "gpt-5.4-mini"

_MAX_HISTORY_TURNS = 6

# Strong off-topic tells that must WIN over the soft on-topic words below — these
# never occur in a genuine city-event message (injection / homework / arithmetic /
# code), so checking them first closes v1's "weak keyword bait flips to allow" gap.
_OFF_TOPIC_STRONG = (
    "zignoruj",
    "instrukcj",
    "prompt systemow",
    "udawaj że",
    "udawaj, że",
    "wypracowanie",
    "esej",
    "podzielone przez",
    "pomnóż",
    "pomnoz",
    "pythonie",
    "python",
    "sortując",
    "sortujac",
)


class GuardrailAgent(GuardrailAgentV1):
    def __init__(
        self,
        openai_client: OpenAIClient,
        model: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        # `model` is accepted for interface compatibility with the loader/harness
        # but DELIBERATELY IGNORED — this version always runs on its own MODEL.
        del model
        super().__init__(openai_client, model=MODEL, system_prompt=system_prompt)

    def check(self, text: str, history: list[dict[str, str]] | None = None) -> GuardrailVerdict:
        t = (text or "").strip()
        if not t:
            return GuardrailVerdict(allow=False, reason="empty", rationale="pusta wiadomość")
        if len(t) > 2000:
            return GuardrailVerdict(allow=False, reason="too_long", rationale="wiadomość zbyt długa")
        low = t.lower()
        if any(bad in low for bad in ("<script", "javascript:", "onerror=")):
            return GuardrailVerdict(allow=False, reason="blocked_content", rationale="niedozwolona treść")

        if not self._client.is_configured:
            return self._offline_topical(low)

        return self._client.complete_structured(
            system=self._system_prompt,
            user=self._with_history(t, history),
            schema=GuardrailVerdict,
            model=self._model,
        )

    @staticmethod
    def _with_history(text: str, history: list[dict[str, str]] | None) -> str:
        """Fold recent turns into the user payload so the model can resolve a
        context-only follow-up. No history → just the message, exactly like v1."""
        if not history:
            return text
        recent = history[-_MAX_HISTORY_TURNS:]
        lines = []
        for turn in recent:
            role = "asystent" if turn.get("role") == "assistant" else "mieszkaniec"
            content = (turn.get("content") or "").strip()
            if content:
                lines.append(f"[{role}]: {content}")
        if not lines:
            return text
        ctx = "\n".join(lines)
        return f"KONTEKST ROZMOWY (poprzednie tury):\n{ctx}\n\nBIEŻĄCA WIADOMOŚĆ:\n{text}"

    @staticmethod
    def _offline_topical(low: str) -> GuardrailVerdict:
        # Strong off-topic signals first — they beat the soft on-topic words.
        if any(k in low for k in _OFF_TOPIC_STRONG):
            return GuardrailVerdict(
                allow=False, reason="off_topic", rationale="poza tematem zdarzeń miejskich (heurystyka offline)"
            )
        return GuardrailAgentV1._offline_topical(low)
