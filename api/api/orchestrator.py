"""Chat orchestrator — the "main agent" that composes the tool elements.

The elements are plain, individually-testable functions (`_guard`, `_extract`,
`_route`, `_search`, `_add`, `build_reply`). Two drivers compose them:

  • `run_turn(...)` — synchronous; the interactive chat REST endpoint calls this
    and gets the structured result back in one request.
  • `chat_turn(ctx)` — the Inngest function; wraps each element in its own durable
    `ctx.step.run` step, so the same pipeline is retried/memoized/traced when run
    in the background. Divide & conquer at runtime.

    INPUT → guardrails → extract (event_extractor → EventUnderstanding) → route
         → search: to_search_filters → events feed  (results shown on the map + cards)
           add:    to_event_draft + missing_fields + a dedup search (never silently
                   drop a report — we surface the likely-existing event).

`guardrails` and `route` are deliberately thin v0 stubs — each a seam meant to
graduate into its own versioned, eval'd agent under `api/ai/`.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

import inngest
from pydantic import BaseModel

from api.bootstrap import Bootstrap, get_bootstrap
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventStatus,
    EventType,
    EventUnderstanding,
    ReportCategory,
    Severity,
    coerce_draft_for_create,
    fields_to_draft,
    merge_drafts,
    missing_fields,
    to_event_draft,
    to_search_filters,
)
from api.inngest_app import EVENT_CHAT_TURN, inngest_client

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

# Nominative labels for the inline-form select options (the accusative
# `_TYPE_LABELS` above are for prose replies, e.g. "chcesz zgłosić awarię").
_TYPE_OPTION_LABELS: dict[EventType, str] = {
    EventType.ISSUE: "Awaria / usterka",
    EventType.ALARM: "Alarm / ostrzeżenie",
    EventType.VENUE: "Miejsce / wydarzenie",
    EventType.PROMOTION: "Promocja",
    EventType.MISSING_PET: "Zaginione zwierzę",
    EventType.HAZARD: "Zagrożenie",
    EventType.OUTAGE: "Przerwa w dostawie",
    EventType.ROADWORKS: "Roboty / utrudnienia",
    EventType.COMMUNITY: "Akcja społeczna",
}
_CATEGORY_OPTION_LABELS: dict[ReportCategory, str] = {
    ReportCategory.WATER: "Woda / kanalizacja",
    ReportCategory.ROADS: "Drogi / chodniki",
    ReportCategory.WASTE: "Odpady / czystość",
    ReportCategory.GREENERY: "Zieleń",
    ReportCategory.LIGHTING: "Oświetlenie",
    ReportCategory.PUBLIC_TRANSPORT: "Transport publiczny",
    ReportCategory.OTHER: "Inne",
}
_SEVERITY_OPTION_LABELS: dict[Severity, str] = {
    Severity.LOW: "Niska",
    Severity.MEDIUM: "Średnia",
    Severity.HIGH: "Wysoka",
    Severity.CRITICAL: "Krytyczna",
}
# Nominative field labels used as the widget's caption.
_FORM_FIELD_LABELS = {
    "type": "Typ zdarzenia",
    "title": "Tytuł",
    "description": "Opis",
    "location": "Lokalizacja",
    "category": "Kategoria",
    "subtype": "Szczegół",
    "starts_at": "Data rozpoczęcia",
}


def _options(labels: dict[Any, str]) -> list[dict[str, str]]:
    return [{"value": member.value, "label": label} for member, label in labels.items()]


def build_add_form(draft: dict[str, Any], missing: list[str]) -> list[dict[str, Any]]:
    """The inline follow-up widgets: one typed control per missing field, so the
    resident completes the report deterministically instead of another free-text
    round-trip. Only the missing fields are asked for — a focused follow-up."""
    raw_type = draft.get("type")
    type_ = (
        raw_type if raw_type is None or isinstance(raw_type, EventType)
        else EventType(raw_type)
    )
    fields: list[dict[str, Any]] = []
    for name in missing:
        spec: dict[str, Any] = {
            "field": name,
            "label": _FORM_FIELD_LABELS.get(name, name),
            "required": True,
        }
        if name == "type":
            spec.update(widget="select", options=_options(_TYPE_OPTION_LABELS))
        elif name == "category":
            spec.update(widget="select", options=_options(_CATEGORY_OPTION_LABELS))
        elif name == "description":
            spec.update(widget="textarea", placeholder="Opisz krótko, co się dzieje…")
        elif name == "location":
            spec.update(widget="text", placeholder="np. ul. Legnicka 1")
        elif name == "starts_at":
            spec.update(widget="datetime")
        elif name == "subtype":
            spec.update(
                widget="text",
                label=(
                    "Gatunek (pies, kot…)"
                    if type_ == EventType.MISSING_PET
                    else "Szczegół"
                ),
                placeholder="np. pies",
            )
        else:  # title (and any future text field)
            spec.update(widget="text", placeholder="Krótki tytuł")
        fields.append(spec)
    return fields


def _plural_events(n: int) -> str:
    if n == 1:
        return "zdarzenie"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "zdarzenia"
    return "zdarzeń"


# -- Elements (thin, deterministic, individually testable) ---------------------

_BLOCKLIST = ("<script", "javascript:", "onerror=")


def _guard(text: str) -> dict[str, Any]:
    """Input guardrails (v0): non-empty, length-bounded, no obvious injection."""
    t = (text or "").strip()
    if not t:
        return {"allow": False, "reason": "empty"}
    if len(t) > 2000:
        return {"allow": False, "reason": "too_long"}
    if any(bad in t.lower() for bad in _BLOCKLIST):
        return {"allow": False, "reason": "blocked_content"}
    return {"allow": True, "reason": "ok"}


_SEARCH_HINTS = (
    "szukaj", "znajd", "pokaż", "pokaz", "czy są", "czy sa", "lista", "filtr",
    "wyszuka", "co się dzieje", "co sie dzieje",
)
_ADD_HINTS = (
    "zgłoś", "zglos", "zgłas", "zglas", "zgłaszam", "zglaszam", "dodaj",
    "zaginął", "zaginal", "znalazłem", "znalazlem", "chcę zgłosić", "chce zglosic",
)


def _extract(
    bootstrap: Bootstrap, text: str, history: list[dict[str, str]] | None = None
) -> EventUnderstanding:
    return bootstrap.event_extractor.extract(text, history=history)


def _prev_intent(history: list[dict[str, str]] | None) -> str | None:
    """The intent of the most recent assistant turn (drives 'continue the flow')."""
    for item in reversed(history or []):
        if item.get("role") == "ASSISTANT":
            return item.get("intent")
    return None


def _answer(bootstrap: Bootstrap, text: str) -> str:
    return bootstrap.assistant_agent.answer(text)


def _route(
    text: str, u: EventUnderstanding, history: list[dict[str, str]] | None = None
) -> str:
    """Route search / add / answer (v0 heuristic; graduates to an eval'd router)."""
    low = (text or "").lower()
    if any(h in low for h in _SEARCH_HINTS):
        return "search"
    # Stay in an add flow already in progress unless the resident clearly pivots,
    # so "to jednak coś innego" continues the report instead of resetting.
    if _prev_intent(history) == "add":
        return "add"
    if any(h in low for h in _ADD_HINTS) or (u.title and (u.location_text or u.address)):
        return "add"
    if u.type is not None:
        return "search"
    return "answer"


def _search(bootstrap: Bootstrap, u: EventUnderstanding) -> tuple[dict[str, Any], list[CityEvent]]:
    filters = to_search_filters(u)
    results = bootstrap.events_service.list_events(**filters)
    return filters, results


def _dedup(bootstrap: Bootstrap, draft: dict[str, Any]) -> list[CityEvent]:
    """Likely-duplicate active events for a draft. Only matches when the draft
    shares BOTH type and category (else a water leak matches a pothole); with no
    category we don't guess — just let the add proceed."""
    raw_type, raw_cat = draft.get("type"), draft.get("category")
    if not raw_type or not raw_cat:
        return []
    type_ = raw_type if isinstance(raw_type, EventType) else EventType(raw_type)
    category = raw_cat if isinstance(raw_cat, ReportCategory) else ReportCategory(raw_cat)
    return bootstrap.events_service.list_events(
        type_=type_,
        category=category,
        district=draft.get("district"),
        status=EventStatus.ACTIVE,
    )[:3]


def _create(bootstrap: Bootstrap, draft: dict[str, Any], reporter_id: int) -> CityEvent:
    """Persist a completed draft as a citizen report. Coordinates are enriched
    afterwards (HERE via Inngest) by the caller — see `run_turn`'s `geocode`."""
    typed = coerce_draft_for_create(draft)
    return bootstrap.events_service.create_event(
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


def _add(
    bootstrap: Bootstrap, u: EventUnderstanding
) -> tuple[dict[str, Any], list[str], list[CityEvent]]:
    """Single-shot add read (used by the background Inngest driver, which has no
    turn-to-turn accumulation or form answers)."""
    draft = to_event_draft(u)
    return draft, missing_fields(draft), _dedup(bootstrap, draft)


# -- Reply templating (deterministic Markdown) ---------------------------------


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


def build_add_reply(draft: dict[str, Any], missing: list[str]) -> str:
    """Reply while still collecting fields — asks for what's missing (rendered as
    the inline form below the message)."""
    label = _type_label(draft.get("type"))
    if missing:
        want = ", ".join(_MISSING_LABELS.get(m, m) for m in missing)
        return f"Rozumiem — chcesz zgłosić **{label}**. Uzupełnij jeszcze: {want}."
    return (
        f"Mam komplet informacji: **{draft.get('title')}** ({label}). "
        "Potwierdź, aby dodać zgłoszenie."
    )


def build_ready_reply(draft: dict[str, Any], dupes: list[CityEvent]) -> str:
    """Reply when the draft is complete — awaiting a final confirm. Surfaces
    likely duplicates first so we never silently drop a report."""
    label = _type_label(draft.get("type"))
    title = draft.get("title")
    if dupes:
        lines = "\n".join(f"- {e.title}" for e in dupes[:3])
        return (
            f"Wygląda na to, że podobne zdarzenie już zgłoszono:\n\n{lines}\n\n"
            f"Jeśli to jednak coś innego, potwierdź — dodam **{title}**."
        )
    return (
        f"Mam komplet informacji: **{title}** ({label}). "
        "Potwierdź, aby dodać zgłoszenie."
    )


# -- Add flow (multi-turn: extract ⊕ prior draft ⊕ inline-form answers) ---------


def _add_turn(
    bootstrap: Bootstrap,
    u: EventUnderstanding,
    *,
    fields: dict[str, Any] | None = None,
    prior_draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One add turn. Accumulates the report from the prior draft, this turn's
    extraction, and this turn's inline-form answers, then either asks for the
    remaining fields (as widgets) or offers to confirm."""
    draft = merge_drafts(prior_draft, to_event_draft(u), fields_to_draft(fields))
    missing = missing_fields(draft)
    if missing:
        return {
            "status": "ok",
            "intent": "add",
            "reply": build_add_reply(draft, missing),
            "draft": draft,
            "missing_fields": missing,
            "form": build_add_form(draft, missing),
        }
    dupes = _dedup(bootstrap, draft)
    return {
        "status": "ok",
        "intent": "add",
        "reply": build_ready_reply(draft, dupes),
        "draft": draft,
        "missing_fields": [],
        "duplicates": dupes,
        "ready": True,
    }


def _confirm_turn(
    bootstrap: Bootstrap,
    prior_draft: dict[str, Any] | None,
    reporter_id: int | None,
    reporter_confirmed: bool,
) -> dict[str, Any]:
    """The resident hit 'confirm'. Gate on a complete draft + a confirmed
    account, then create the event (coordinates enriched afterwards)."""
    draft = prior_draft or {}
    missing = missing_fields(draft)
    if missing:
        return {
            "status": "ok",
            "intent": "add",
            "reply": "Zanim dodam zgłoszenie, uzupełnij brakujące pola.",
            "draft": draft,
            "missing_fields": missing,
            "form": build_add_form(draft, missing),
        }
    if reporter_id is None:
        return {
            "status": "login_required",
            "intent": "add",
            "reply": "Aby dodać zgłoszenie, zaloguj się na swoje konto.",
            "draft": draft,
            "ready": True,
        }
    if not reporter_confirmed:
        return {
            "status": "email_unconfirmed",
            "intent": "add",
            "reply": "Potwierdź adres e-mail, aby móc dodawać zgłoszenia.",
            "draft": draft,
            "ready": True,
        }
    event = _create(bootstrap, draft, reporter_id)
    return {
        "status": "ok",
        "intent": "add",
        "reply": f"✅ Dodano zgłoszenie: **{event.title}**. Dziękujemy!",
        "created": event,
        "geocode": bool(event.location_text or event.address),
    }


def _block_reply(reason: str) -> str:
    if reason == "empty":
        return "Napisz, czego szukasz albo co chcesz zgłosić."
    if reason == "too_long":
        return "Wiadomość jest za długa — skróć ją, proszę."
    return "Nie mogę przetworzyć tej wiadomości."


# -- Synchronous driver (interactive chat REST) --------------------------------


def run_turn(
    bootstrap: Bootstrap,
    text: str,
    history: list[dict[str, str]] | None = None,
    *,
    fields: dict[str, Any] | None = None,
    action: str | None = None,
    prior_draft: dict[str, Any] | None = None,
    reporter_id: int | None = None,
    reporter_confirmed: bool = False,
) -> dict[str, Any]:
    """Full pipeline, synchronous. `history` (prior turns, each optionally carrying
    its `intent`) gives the agent memory. The add flow also threads:
      • `fields` — inline-form answers submitted this turn (structured, exact),
      • `prior_draft` — the report accumulated so far (from the conversation),
      • `action="confirm"` + `reporter_id`/`reporter_confirmed` — the final commit.
    Returns a JSON-encodable result."""
    # A pure confirm/commit turn — no text to extract or route.
    if action == "confirm":
        return _confirm_turn(bootstrap, prior_draft, reporter_id, reporter_confirmed)

    # Inline-form answers count as structured input, so an empty text box is fine.
    has_fields = bool(fields)
    guard = _guard(text)
    if not guard["allow"] and not has_fields:
        return {"status": "blocked", "reason": guard["reason"], "reply": _block_reply(guard["reason"])}

    u = _extract(bootstrap, text, history)
    # Answering the inline form always continues the add flow.
    intent = "add" if has_fields else _route(text, u, history)

    if intent == "search":
        filters, results = _search(bootstrap, u)
        return {
            "status": "ok",
            "intent": "search",
            "reply": build_search_reply(results),
            "filters": filters,
            "results": results,
        }

    if intent == "add":
        return _add_turn(bootstrap, u, fields=fields, prior_draft=prior_draft)

    return {"status": "ok", "intent": "answer", "reply": _answer(bootstrap, text)}


# -- Inngest driver (durable / observable — one step per element) --------------


def _jsonify(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    return value


@inngest_client.create_function(
    fn_id="chat-turn",
    trigger=inngest.TriggerEvent(event=EVENT_CHAT_TURN),
    retries=1,
)
async def chat_turn(ctx: inngest.Context) -> dict[str, Any]:
    text = str(ctx.event.data.get("text", ""))
    bootstrap = get_bootstrap()

    guard = await ctx.step.run("guardrails", lambda: _guard(text))
    if not guard["allow"]:
        return {"status": "blocked", "reason": guard["reason"], "reply": _block_reply(guard["reason"])}

    understanding = await ctx.step.run(
        "extract", lambda: _extract(bootstrap, text).model_dump(mode="json")
    )
    u = EventUnderstanding.model_validate(understanding)
    intent = await ctx.step.run("route", lambda: _route(text, u))

    if intent == "search":
        def _search_step() -> dict[str, Any]:
            filters, results = _search(bootstrap, u)
            return {
                "reply": build_search_reply(results),
                "filters": _jsonify(filters),
                "results": [e.model_dump(mode="json") for e in results],
            }

        payload = await ctx.step.run("search", _search_step)
        return {"status": "ok", "intent": "search", **payload}

    if intent == "add":
        payload = await ctx.step.run(
            "add", lambda: _jsonify(_add_turn(bootstrap, u))
        )
        return payload

    reply = await ctx.step.run("answer", lambda: _answer(bootstrap, text))
    return {"status": "ok", "intent": "answer", "reply": reply}


CHAT_INNGEST_FUNCTIONS = [chat_turn]
