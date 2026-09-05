"""event_extractor · v1 — LLM extraction with an offline keyword fallback.

With an OpenAI key it asks for a structured `EventUnderstanding`; without one it
falls back to the keyword table for the `category` field (other fields left
unset) so the agent — and the DeepEval loop under `eval/` — still runs offline in
local dev. Either way the output is only a PROPOSAL for a human.

The keyword table is intentionally the whole offline "model" for category: it is
the baseline the eval scores, and the number Claude Code (or a prompt optimiser)
tries to beat when it edits this file. Keep it readable — it is meant to be diffed.
"""

from api.adapters.llm import OpenAIClient
from api.ai.event_extractor.base import AbstractEventExtractor
from api.ai.event_extractor.versions.v1.prompts import SYSTEM_PROMPT
from api.contexts_boundaries.city_events_bc.models import (
    EventUnderstanding,
    ReportCategory,
)

# Scan order = priority. First matching row wins the primary slot; any further
# matches become secondary categories. Polish stems (substring match, lower-cased)
# so inflected forms hit too (e.g. "dziur" catches dziura/dziury/dziurę).
_KEYWORDS: list[tuple[tuple[str, ...], ReportCategory]] = [
    (
        (
            "woda",
            "wod",
            "wyciek",
            "hydrant",
            "kanaliz",
            "ściek",
            "sciek",
            "wilgo",
            "przeciek",
            "zalan",
            "zalew",
            "kałuż",
            "kaluz",
            "studzienk",
            "deszczów",
            "wodociąg",
            "wodociag",
            "rura",
            "rur ",
        ),
        ReportCategory.WATER,
    ),
    (
        (
            "droga",
            "drog",
            "dziura",
            "dziur",
            "jezdni",
            "chodnik",
            "asfalt",
            "wybój",
            "wyboj",
            "nawierzchni",
            "krawężnik",
            "kraweznik",
            "koleina",
            "ubytek",
            "znak drog",
            "sygnalizacj",
            "próg zwal",
            "prog zwal",
            "pas ruchu",
        ),
        ReportCategory.ROADS,
    ),
    (
        (
            "śmiec",
            "smiec",
            "odpad",
            "kosz",
            "wysypisk",
            "kontener",
            "gruz",
            "wywóz",
            "wywoz",
            "przepełnion",
            "przepelnion",
            "sprzątan",
            "sprzatan",
            "wysyp",
        ),
        ReportCategory.WASTE,
    ),
    (
        (
            "drzew",
            "krzew",
            "trawnik",
            "park ",
            "parku",
            "zieleń",
            "zielen",
            "gałą",
            "gala",
            "gałęz",
            "galez",
            "liści",
            "lisci",
            "chwast",
            "koszen",
            "nasadzen",
            "żywopłot",
            "zywoplot",
        ),
        ReportCategory.GREENERY,
    ),
    (
        (
            "latarni",
            "lampa",
            "lamp ",
            "oświetl",
            "oswietl",
            "ciemno",
            "żarówk",
            "zarowk",
            "nie świeci",
            "nie swieci",
            "przepalon",
            "słup oświetl",
            "slup oswietl",
            "punkt świetl",
        ),
        ReportCategory.LIGHTING,
    ),
    (
        (
            "tramwaj",
            "autobus",
            "mpk",
            "przystan",
            "rozkład",
            "rozklad",
            "biletomat",
            "bilet",
            "komunikacj",
            "linia ",
            "linii",
            "kursuj",
            "opóźni",
            "opozni",
            "wiata przyst",
        ),
        ReportCategory.PUBLIC_TRANSPORT,
    ),
]


def _dedupe(cats: list[ReportCategory]) -> list[ReportCategory]:
    seen: set[ReportCategory] = set()
    out: list[ReportCategory] = []
    for c in cats:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


class EventExtractor(AbstractEventExtractor):
    def __init__(
        self,
        openai_client: OpenAIClient,
        model: str | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._system_prompt = system_prompt

    def extract(
        self,
        text: str,
        citizen_category: ReportCategory | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> EventUnderstanding:
        if not self._client.is_configured:
            return self._offline_extract(text, citizen_category)

        convo = ""
        if history:
            lines = [
                f"{'Mieszkaniec' if h.get('role') == 'USER' else 'Asystent'}: {h.get('content', '')}"
                for h in history
            ]
            convo = "Dotychczasowa rozmowa:\n" + "\n".join(lines) + "\n\n"
        user = (
            f"{convo}"
            f"Najnowsza wiadomość mieszkańca: {text}\n"
            f"Kategoria wskazana przez mieszkańca: "
            f"{citizen_category.value if citizen_category else 'brak'}\n"
            "Wydobądź JEDNO zdarzenie z całej rozmowy — akumuluj informacje z "
            "wcześniejszych wiadomości (np. lokalizację podaną wcześniej)."
        )
        result = self._client.complete_structured(
            system=self._system_prompt,
            user=user,
            schema=EventUnderstanding,
            model=self._model,
        )
        # Keep the payload tidy: category must not repeat inside secondary.
        result.secondary_categories = [
            c for c in _dedupe(result.secondary_categories) if c != result.category
        ]
        return result

    def _offline_extract(
        self, text: str, citizen_category: ReportCategory | None
    ) -> EventUnderstanding:
        low = text.lower()
        matched = _dedupe(
            [cat for keywords, cat in _KEYWORDS if any(k in low for k in keywords)]
        )

        if citizen_category is not None:
            category = citizen_category
            secondary = [c for c in matched if c != category]
            confidence = 0.40
            rationale = "kategoria wskazana przez mieszkańca (heurystyka offline)"
        elif matched:
            category, secondary = matched[0], matched[1:]
            confidence = 0.35
            rationale = "dopasowanie słów kluczowych (heurystyka offline)"
        else:
            # OTHER is the offline catch-all — preserves the scored category baseline.
            category, secondary = ReportCategory.OTHER, []
            confidence = 0.20
            rationale = "brak dopasowania słów kluczowych → OTHER (heurystyka offline)"

        hits = [k for keywords, _ in _KEYWORDS for k in keywords if k in low]
        return EventUnderstanding(
            category=category,
            secondary_categories=secondary,
            keywords=hits[:8],
            summary=text.strip() or None,
            confidence=confidence,
            rationale=rationale,
        )
