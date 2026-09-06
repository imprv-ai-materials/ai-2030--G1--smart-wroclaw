"""report_agent · v1 — deterministic multi-turn draft completion + dedup.

Gathers a city-event report across turns: prior draft ⊕ this turn's extraction ⊕
inline-form answers (`merge_drafts`), checks it against the per-type required fields
(`missing_fields`), and either asks for what's missing as an inline form the frontend
renders, or — when complete — surfaces likely duplicates before create. Pure logic +
one repo read; no LLM. The create itself stays a service call in the orchestrator.
"""

from __future__ import annotations

from typing import Any

from api.ai.report_agent.base import AbstractReportAgent, ReportTurn
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventStatus,
    EventType,
    EventUnderstanding,
    ReportCategory,
    fields_to_draft,
    merge_drafts,
    missing_fields,
    to_event_draft,
)
from api.contexts_boundaries.city_events_bc.repositories import AbstractEventsRepository

# Nominative field captions for the inline follow-up widgets.
_FIELD_LABELS = {
    "type": "Typ zdarzenia",
    "title": "Tytuł",
    "description": "Opis",
    "location": "Lokalizacja",
    "category": "Kategoria",
    "subtype": "Szczegół",
    "starts_at": "Data rozpoczęcia",
}
_TYPE_OPTIONS = [{"value": t.value, "label": t.value} for t in EventType]
_CATEGORY_OPTIONS = [{"value": c.value, "label": c.value} for c in ReportCategory]


class ReportAgent(AbstractReportAgent):
    def __init__(self, events_repository: AbstractEventsRepository) -> None:
        self._events = events_repository

    def plan_turn(
        self,
        understanding: EventUnderstanding,
        *,
        prior_draft: dict[str, Any] | None = None,
        fields: dict[str, Any] | None = None,
    ) -> ReportTurn:
        draft = merge_drafts(prior_draft, to_event_draft(understanding), fields_to_draft(fields))
        missing = missing_fields(draft)
        if missing:
            return ReportTurn(draft=draft, missing_fields=missing, form=self._build_form(draft, missing), ready=False)
        return ReportTurn(draft=draft, missing_fields=[], form=[], ready=True, duplicates=self._dedup(draft))

    def _build_form(self, draft: dict[str, Any], missing: list[str]) -> list[dict[str, Any]]:
        """One typed widget per missing field so the resident completes the report
        deterministically instead of another free-text round-trip."""
        raw_type = draft.get("type")
        type_ = raw_type if raw_type is None or isinstance(raw_type, EventType) else EventType(raw_type)
        out: list[dict[str, Any]] = []
        for name in missing:
            spec: dict[str, Any] = {"field": name, "label": _FIELD_LABELS.get(name, name), "required": True}
            if name == "type":
                spec |= {"widget": "select", "options": _TYPE_OPTIONS}
            elif name == "category":
                spec |= {"widget": "select", "options": _CATEGORY_OPTIONS}
            elif name == "description":
                spec |= {"widget": "textarea", "placeholder": "Opisz krótko, co się dzieje…"}
            elif name == "location":
                spec |= {"widget": "text", "placeholder": "np. ul. Legnicka 1"}
            elif name == "starts_at":
                spec |= {"widget": "datetime"}
            elif name == "subtype":
                spec |= {
                    "widget": "text",
                    "label": "Gatunek (pies, kot…)" if type_ == EventType.MISSING_PET else "Szczegół",
                    "placeholder": "np. pies",
                }
            else:  # title (and any future text field)
                spec |= {"widget": "text", "placeholder": "Krótki tytuł"}
            out.append(spec)
        return out

    def _dedup(self, draft: dict[str, Any]) -> list[CityEvent]:
        """Likely-duplicate active events for a complete draft. Requires BOTH type
        and category (else a water leak matches a pothole); no category → don't guess."""
        raw_type, raw_cat = draft.get("type"), draft.get("category")
        if not raw_type or not raw_cat:
            return []
        type_ = raw_type if isinstance(raw_type, EventType) else EventType(raw_type)
        category = raw_cat if isinstance(raw_cat, ReportCategory) else ReportCategory(raw_cat)
        return self._events.list(
            status=EventStatus.ACTIVE, type_=type_, category=category, district=draft.get("district")
        )[:3]
