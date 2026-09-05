"""EventUnderstanding — the structured reading of an open-text citizen message.

Produced by the `event_extractor` agent (open text → this one object), then fed
to two PURE projections that both chat tools consume:
  • `to_search_filters` → the events-feed filter  (the *search* tool's input)
  • `to_event_draft`    → a create-event payload   (the *add* tool's input)

Coordinates are deliberately absent: extraction yields `address`/`location_text`,
and the HERE geocoder + Inngest enrichment turn those into `lat/lng` downstream —
so the extractor stays a pure text→struct unit, testable in isolation. `category`
(the agent's original single job) is now just one field here, so the curated
category dataset/baseline keeps scoring it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from api.contexts_boundaries.city_events_bc.models.enums import (
    EventType,
    ReportCategory,
    Severity,
)


class EventUnderstanding(BaseModel):
    """Intent-agnostic structured reading of one message (search OR add).

    Every field is optional: `None`/empty means "not stated". Downstream, the
    router decides search vs add and the relevant projection shapes this into the
    tool's input; `missing_fields` reads it against per-type requirements.
    """

    # what
    type: EventType | None = None
    category: ReportCategory | None = None
    secondary_categories: list[ReportCategory] = Field(default_factory=list)
    subtype: str | None = None
    severity: Severity | None = None
    # where (geocoded to lat/lng downstream — not extracted here)
    location_text: str | None = None
    address: str | None = None
    district: str | None = None
    # when
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # content
    title: str | None = None
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)
    # meta
    confidence: float = 0.0
    rationale: str = ""


# Required fields per event type — drives missing-field detection for `add`.
# `location` is a virtual field satisfied by either location_text OR address.
_BASE_REQUIRED: tuple[str, ...] = ("type", "title", "description", "location")
REQUIRED_FIELDS: dict[EventType, tuple[str, ...]] = {
    EventType.ISSUE: _BASE_REQUIRED + ("category",),
    EventType.ALARM: _BASE_REQUIRED,
    EventType.VENUE: _BASE_REQUIRED + ("starts_at",),
    EventType.PROMOTION: _BASE_REQUIRED,
    EventType.MISSING_PET: _BASE_REQUIRED + ("subtype",),
    EventType.HAZARD: _BASE_REQUIRED,
    EventType.OUTAGE: _BASE_REQUIRED,
    EventType.ROADWORKS: _BASE_REQUIRED,
    EventType.COMMUNITY: _BASE_REQUIRED + ("starts_at",),
}


def to_search_filters(u: EventUnderstanding) -> dict[str, Any]:
    """Project onto `EventsService.list_events` kwargs (the search tool input).

    OTHER is treated as "unspecified" for filtering — the extractor uses it as a
    catch-all (and the eval scores it), but it must not over-constrain a search.
    """
    category = (
        u.category
        if u.category is not None and u.category != ReportCategory.OTHER
        else None
    )
    # Free-text `q` is a substring match, so it only helps when there's nothing
    # structured to filter on — otherwise it double-counts (e.g. "awarie Krzyki"
    # over ISSUE+Krzyki) and zeroes out the results. Structured wins; else q.
    has_structure = u.type is not None or category is not None or u.district is not None
    q = None if has_structure else (" ".join(u.keywords).strip() or (u.summary or "").strip() or None)
    return {"type_": u.type, "category": category, "district": u.district, "q": q}


def to_event_draft(u: EventUnderstanding) -> dict[str, Any]:
    """Project onto a create-event payload (the add tool input)."""
    return {
        "type": u.type,
        "title": u.title,
        "description": u.summary,
        "category": u.category,
        "severity": u.severity,
        "subtype": u.subtype,
        "location_text": u.location_text,
        "address": u.address,
        "district": u.district,
        "starts_at": u.starts_at,
        "ends_at": u.ends_at,
    }


def missing_fields(draft: dict[str, Any]) -> list[str]:
    """Required fields (per the draft's type) the draft doesn't yet fill."""
    raw_type = draft.get("type")
    if raw_type is None:
        return ["type"]
    type_ = raw_type if isinstance(raw_type, EventType) else EventType(raw_type)
    missing: list[str] = []
    for field in REQUIRED_FIELDS.get(type_, _BASE_REQUIRED):
        if field == "location":
            if not (draft.get("location_text") or draft.get("address")):
                missing.append("location")
        elif not draft.get(field):
            missing.append(field)
    return missing


# -- Accumulating a draft across turns (inline follow-up widgets) ---------------
#
# The add flow collects fields over several turns: free text (re-extracted each
# turn) PLUS the inline form widgets (exact, structured answers). Widget answers
# aren't natural language, so they can't be recovered by re-extraction — instead
# the merged draft is carried in the conversation and re-merged here. These are
# PURE (no I/O), so each is unit-testable in isolation.

_EMPTY = (None, "", [])


def fields_to_draft(fields: dict[str, Any] | None) -> dict[str, Any]:
    """Map inline-form widget answers onto draft keys, coercing enums.

    The widget `field` names mirror the draft keys, except `location` (a virtual
    required field) writes to `address`. Blank answers are dropped so a skipped
    widget never clobbers a value we already have.
    """
    out: dict[str, Any] = {}
    for key, raw in (fields or {}).items():
        if raw in _EMPTY:
            continue
        if key == "type":
            out["type"] = raw if isinstance(raw, EventType) else EventType(raw)
        elif key == "category":
            out["category"] = raw if isinstance(raw, ReportCategory) else ReportCategory(raw)
        elif key == "severity":
            out["severity"] = raw if isinstance(raw, Severity) else Severity(raw)
        elif key == "location":
            out["address"] = raw
        elif key in (
            "title", "description", "subtype", "address",
            "location_text", "district", "starts_at", "ends_at",
        ):
            out[key] = raw
    return out


def merge_drafts(*drafts: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay drafts left→right; a later non-empty value wins, and None/empty
    never clobbers an earlier value. This is how a report accumulates: prior
    draft ⊕ this turn's extraction ⊕ this turn's widget answers."""
    merged: dict[str, Any] = {}
    for draft in drafts:
        if not draft:
            continue
        for key, value in draft.items():
            if value not in _EMPTY:
                merged[key] = value
    return merged


def coerce_draft_for_create(draft: dict[str, Any]) -> dict[str, Any]:
    """Turn a merged draft (whose enums/dates may be plain strings after a JSON
    round-trip through the stored conversation) into typed `create_event` kwargs.
    `type` becomes `type_` to match the service signature."""
    out = dict(draft)
    raw_type = out.pop("type", None)
    out["type_"] = (
        raw_type if raw_type is None or isinstance(raw_type, EventType)
        else EventType(raw_type)
    )
    for key, enum in (("category", ReportCategory), ("severity", Severity)):
        value = out.get(key)
        if value is not None and not isinstance(value, enum):
            out[key] = enum(value)
    for key in ("starts_at", "ends_at"):
        value = out.get(key)
        if isinstance(value, str):
            out[key] = datetime.fromisoformat(value)
    return out
