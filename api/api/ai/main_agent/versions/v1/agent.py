"""main_agent · v1 — composes the sub-agents into one interactive turn.

    text (+history, +form fields, +confirm) ──▶
        guardrails ─ reject → refusal
            └ extractor → EventUnderstanding
                └ router → search | report | analytics
                    ├ search    : search_agent → ranked events (+ filters for the map)
                    ├ report    : report_agent → draft + inline form | ready → create
                    └ analytics : geo_resolver → scope, analytics_agent → count + reply

Each element is one of the versioned sub-agents; this module only sequences them and
templates the deterministic Markdown reply. The create-on-confirm is a service call.
"""

from __future__ import annotations

from typing import Any

from api.ai.analytics_agent import AbstractAnalyticsAgent
from api.ai.event_extractor import AbstractEventExtractor
from api.ai.geo_resolver import AbstractGeoResolver
from api.ai.guardrails_agent import AbstractGuardrailAgent
from api.ai.main_agent.base import AbstractMainAgent
from api.ai.report_agent import AbstractReportAgent
from api.ai.router_agent import AbstractRouterAgent
from api.ai.search_agent import AbstractSearchAgent
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventType,
    EventUnderstanding,
    coerce_draft_for_create,
    to_search_filters,
)
from api.contexts_boundaries.city_events_bc.services import EventsService

# -- Polish reply vocabulary ---------------------------------------------------

_TYPE_LABELS: dict[EventType, str] = {
    EventType.ISSUE: "awarię",
    EventType.ALARM: "alarm",
    EventType.VENUE: "miejsce / wydarzenie",
    EventType.PROMOTION: "promocję",
    EventType.MISSING_PET: "zaginione zwierzę",
    EventType.HAZARD: "zagrożenie",
    EventType.OUTAGE: "przerwę w dostawie",
    EventType.ROADWORKS: "roboty / utrudnienia",
    EventType.COMMUNITY: "akcję społeczną",
}
_MISSING_LABELS = {
    "type": "typ zdarzenia",
    "title": "tytuł",
    "description": "opis",
    "location": "lokalizację",
    "category": "kategorię",
    "subtype": "szczegół",
    "starts_at": "datę rozpoczęcia",
}


def _plural_events(n: int) -> str:
    if n == 1:
        return "zdarzenie"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "zdarzenia"
    return "zdarzeń"


def _type_label(type_: EventType | str | None) -> str:
    if type_ is None:
        return "zdarzenie"
    if not isinstance(type_, EventType):
        try:
            type_ = EventType(type_)
        except ValueError:
            return "zdarzenie"
    return _TYPE_LABELS.get(type_, "zdarzenie")


def build_search_reply(results: list[CityEvent]) -> str:
    n = len(results)
    if n == 0:
        return "Nie znalazłem pasujących zdarzeń. Spróbuj opisać to inaczej."
    return f"Znalazłem **{n}** {_plural_events(n)} — pokazuję je na mapie i poniżej."


def build_report_reply(draft: dict[str, Any], missing: list[str]) -> str:
    label = _type_label(draft.get("type"))
    if missing:
        want = ", ".join(_MISSING_LABELS.get(m, m) for m in missing)
        return f"Rozumiem — chcesz zgłosić **{label}**. Uzupełnij jeszcze: {want}."
    return f"Mam komplet informacji: **{draft.get('title')}** ({label}). Potwierdź, aby dodać zgłoszenie."


def build_ready_reply(draft: dict[str, Any], dupes: list[CityEvent]) -> str:
    label = _type_label(draft.get("type"))
    title = draft.get("title")
    if dupes:
        lines = "\n".join(f"- {e.title}" for e in dupes[:3])
        return (
            f"Wygląda na to, że podobne zdarzenie już zgłoszono:\n\n{lines}\n\n"
            f"Jeśli to jednak coś innego, potwierdź — dodam **{title}**."
        )
    return f"Mam komplet informacji: **{title}** ({label}). Potwierdź, aby dodać zgłoszenie."


def block_reply(reason: str) -> str:
    if reason == "empty":
        return "Napisz, czego szukasz albo co chcesz zgłosić."
    if reason == "too_long":
        return "Wiadomość jest za długa — skróć ją, proszę."
    if reason == "off_topic":
        return (
            "Jestem asystentem miejskim Wrocławia — pomagam zgłaszać i wyszukiwać zdarzenia "
            "oraz podawać statystyki. Zadaj proszę pytanie dotyczące miasta."
        )
    return "Nie mogę przetworzyć tej wiadomości."


class MainAgent(AbstractMainAgent):
    def __init__(
        self,
        *,
        guardrails: AbstractGuardrailAgent,
        extractor: AbstractEventExtractor,
        router: AbstractRouterAgent,
        search: AbstractSearchAgent,
        report: AbstractReportAgent,
        analytics: AbstractAnalyticsAgent,
        geo: AbstractGeoResolver,
        events_service: EventsService,
    ) -> None:
        self._guardrails = guardrails
        self._extractor = extractor
        self._router = router
        self._search = search
        self._report = report
        self._analytics = analytics
        self._geo = geo
        self._events = events_service

    def run_turn(
        self,
        text: str,
        history: list[dict[str, str]] | None = None,
        *,
        fields: dict[str, Any] | None = None,
        action: str | None = None,
        prior_draft: dict[str, Any] | None = None,
        reporter_id: int | None = None,
        reporter_confirmed: bool = False,
    ) -> dict[str, Any]:
        # A pure confirm/commit turn — no text to guard, extract or route.
        if action == "confirm":
            return self._confirm_turn(prior_draft, reporter_id, reporter_confirmed)

        # Inline-form answers are structured input, so an empty text box is fine.
        has_fields = bool(fields)
        verdict = self._guardrails.check(text, history)
        if not verdict.allow and not has_fields:
            return {"status": "blocked", "reason": verdict.reason, "reply": block_reply(verdict.reason)}

        u = self._extractor.extract(text, history=history)
        # Answering the inline form always continues the report flow.
        intent = "report" if has_fields else self._router.route(text, u, history).intent.value

        if intent == "report":
            return self._report_turn(u, fields=fields, prior_draft=prior_draft)
        if intent == "analytics":
            return self._analytics_turn(u, text)
        return self._search_turn(u)  # search is also the defensive default

    # -- lanes ----------------------------------------------------------------
    def _search_turn(self, u: EventUnderstanding) -> dict[str, Any]:
        results = self._search.search(u)
        return {
            "status": "ok",
            "intent": "search",
            "reply": build_search_reply(results),
            "filters": to_search_filters(u),  # the UI lifts these to the map
            "results": results,
        }

    def _report_turn(
        self, u: EventUnderstanding, *, fields: dict[str, Any] | None, prior_draft: dict[str, Any] | None
    ) -> dict[str, Any]:
        turn = self._report.plan_turn(u, prior_draft=prior_draft, fields=fields)
        if turn.missing_fields:
            return {
                "status": "ok",
                "intent": "report",
                "reply": build_report_reply(turn.draft, turn.missing_fields),
                "draft": turn.draft,
                "missing_fields": turn.missing_fields,
                "form": turn.form,
            }
        return {
            "status": "ok",
            "intent": "report",
            "reply": build_ready_reply(turn.draft, turn.duplicates),
            "draft": turn.draft,
            "missing_fields": [],
            "duplicates": turn.duplicates,
            "ready": True,
        }

    def _analytics_turn(self, u: EventUnderstanding, text: str) -> dict[str, Any]:
        hint = u.location_text or u.address or u.district or text
        resolved = self._geo.resolve(hint) if hint else None
        # A "near me" scope needs the user's own coordinates (not available here yet),
        # so fall back to a whole-city count rather than an unbounded radius.
        scope = None
        if resolved is not None and not resolved.needs_user_location:
            scope = {
                "district": resolved.district,
                "lat": resolved.lat,
                "lng": resolved.lng,
                "radius_m": resolved.radius_m,
            }
        answer = self._analytics.answer(u, scope=scope)
        return {
            "status": "ok",
            "intent": "analytics",
            "reply": answer.reply,
            "count": answer.count,
            "breakdown": answer.breakdown,
        }

    # -- confirm / create -----------------------------------------------------
    def _confirm_turn(
        self, prior_draft: dict[str, Any] | None, reporter_id: int | None, reporter_confirmed: bool
    ) -> dict[str, Any]:
        draft = prior_draft or {}
        # Re-plan from the accumulated draft to recompute missing fields + form.
        turn = self._report.plan_turn(EventUnderstanding(), prior_draft=draft)
        if turn.missing_fields:
            return {
                "status": "ok",
                "intent": "report",
                "reply": "Zanim dodam zgłoszenie, uzupełnij brakujące pola.",
                "draft": turn.draft,
                "missing_fields": turn.missing_fields,
                "form": turn.form,
            }
        if reporter_id is None:
            return {
                "status": "login_required",
                "intent": "report",
                "reply": "Aby dodać zgłoszenie, zaloguj się na swoje konto.",
                "draft": draft,
                "ready": True,
            }
        if not reporter_confirmed:
            return {
                "status": "email_unconfirmed",
                "intent": "report",
                "reply": "Potwierdź adres e-mail, aby móc dodawać zgłoszenia.",
                "draft": draft,
                "ready": True,
            }
        event = self._create(draft, reporter_id)
        return {
            "status": "ok",
            "intent": "report",
            "reply": f"✅ Dodano zgłoszenie: **{event.title}**. Dziękujemy!",
            "created": event,
            "geocode": bool(event.location_text or event.address),
        }

    def _create(self, draft: dict[str, Any], reporter_id: int) -> CityEvent:
        """Persist a completed draft. Coordinates are enriched afterwards (HERE via
        Inngest) by the caller — see the chat router's `geocode` signal."""
        typed = coerce_draft_for_create(draft)
        return self._events.create_event(
            type_=typed["type_"],
            title=typed["title"],
            description=typed["description"],
            reporter_id=reporter_id,
            category=typed.get("category"),
            severity=typed.get("severity"),
            subtype=typed.get("subtype"),
            location_text=typed.get("location_text"),
            address=typed.get("address"),
            district=typed.get("district"),
            starts_at=typed.get("starts_at"),
            ends_at=typed.get("ends_at"),
        )
