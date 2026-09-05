"""triage_agent · v1 — LLM classification with an offline keyword fallback.

With an OpenAI key it asks for a structured `TriageResult`; without one it routes
by keyword so the specialist queue still fills with reviewable proposals in local
dev. Either way the output is only a PROPOSAL for the human specialist.
"""

from api.adapters.llm import OpenAIClient
from api.ai.triage_agent.base import AbstractTriageAgent
from api.ai.triage_agent.versions.v1.prompts import SYSTEM_PROMPT
from api.contexts_boundaries.city_events_bc.models import (
    IssueReport,
    ReportCategory,
    Severity,
    TriageResult,
)

# Keyword → (category, department) for the offline heuristic fallback.
_KEYWORDS: list[tuple[tuple[str, ...], ReportCategory, str]] = [
    (("woda", "wyciek", "hydrant", "kanaliz", "ścieki", "wilgo"), ReportCategory.WATER, "MPWiK"),
    (("droga", "dziura", "jezdni", "chodnik", "asfalt", "wybój"), ReportCategory.ROADS, "ZDiUM"),
    (("śmiec", "odpad", "kosz", "wysypisk", "kontener"), ReportCategory.WASTE, "Ekosystem"),
    (("drzewo", "krzew", "trawnik", "park", "zieleń", "gałą"), ReportCategory.GREENERY, "Zarząd Zieleni Miejskiej"),
    (("latarnia", "lampa", "oświetl", "ciemno", "żarówk"), ReportCategory.LIGHTING, "ZDiUM"),
    (("tramwaj", "autobus", "mpk", "przystanek", "rozkład"), ReportCategory.PUBLIC_TRANSPORT, "MPK Wrocław"),
]

_CRITICAL_HINTS = ("zagroż", "wypadek", "iskrz", "gaz", "zalanie", "pożar", "porażen")


class TriageAgent(AbstractTriageAgent):
    def __init__(
        self,
        openai_client: OpenAIClient,
        model: str | None = None,
        default_department: str = "",
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._default_department = default_department
        self._system_prompt = system_prompt

    def triage(self, report: IssueReport) -> TriageResult:
        if not self._client.is_configured:
            return self._offline_triage(report)

        user = (
            f"Tytuł: {report.title}\n"
            f"Opis: {report.description}\n"
            f"Kategoria wskazana przez mieszkańca: {report.category.value if report.category else 'brak'}\n"
            f"Lokalizacja: {report.location_text or 'nie podano'}"
        )
        return self._client.complete_structured(
            system=self._system_prompt, user=user, schema=TriageResult, model=self._model
        )

    def _offline_triage(self, report: IssueReport) -> TriageResult:
        text = f"{report.title} {report.description}".lower()

        category = report.category or ReportCategory.OTHER
        department = self._default_department
        for keywords, cat, dept in _KEYWORDS:
            if any(k in text for k in keywords):
                category = report.category or cat
                department = dept
                break

        severity = Severity.CRITICAL if any(h in text for h in _CRITICAL_HINTS) else Severity.MEDIUM

        return TriageResult(
            category=category,
            severity=severity,
            department=department or self._default_department,
            summary=f"Zgłoszenie mieszkańca: {report.title.strip()}",
            suggested_response=(
                "Dziękujemy za zgłoszenie. Przekazaliśmy je do właściwej jednostki miejskiej "
                "i zajmiemy się sprawą w możliwie najkrótszym terminie. O postępach będziemy "
                "informować pod tym zgłoszeniem."
            ),
            is_duplicate=False,
            # Low confidence — it's only a keyword guess, so the specialist knows
            # to look closely.
            confidence=0.35,
        )
