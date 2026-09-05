"""EventsService — the citizen city-map feed.

Read side is public (the map + "aktywne zdarzenia" list). Writes come from two
places: a logged-in, email-confirmed resident filing an event, and the seed /
ingest path that bulk-loads demo data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from api.adapters.geocoding import HereGeocodingClient
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventSource,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from api.contexts_boundaries.city_events_bc.repositories import AbstractEventsRepository
from api.shared.exceptions import AccessDeniedError, NotFoundError

# How long a freshly filed event stays on the map before it drops off. Residents
# routinely file events and never come back to close them, so anything a citizen
# posts auto-expires after this window unless they explicitly prolong it. The
# author can extend it (see `prolong_event`); city/seed events set their own
# `expires_at` (usually none) and are unaffected.
EVENT_DEFAULT_TTL = timedelta(hours=24)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)

# The full column set a `city_events` insert may touch. `create_many` keys off
# the first row, so every ingested row is normalised to exactly these keys.
_COLUMNS = (
    "type",
    "status",
    "title",
    "description",
    "category",
    "severity",
    "location_text",
    "address",
    "lat",
    "lng",
    "source",
    "reporter_id",
    "starts_at",
    "ends_at",
    # structured / reportable columns (migration 0005)
    "subtype",
    "district",
    "resolved_at",
    "expires_at",
    "confirmations",
    "verified",
    "contact_phone",
    "image_url",
    "details",
)

# Columns that are NOT NULL in the DB (with a default). Because `_normalize`
# forces a fixed key set, an absent value would otherwise be inserted as an
# explicit NULL and override the column default — so we fill these ourselves.
_NOT_NULL_DEFAULTS: dict[str, Any] = {
    "confirmations": 0,
    "verified": False,
    "details": {},
}


class EventsService:
    def __init__(
        self,
        events_repository: AbstractEventsRepository,
        geocoding_client: HereGeocodingClient | None = None,
    ) -> None:
        self._events = events_repository
        self._geocoder = geocoding_client

    def list_events(
        self,
        status: EventStatus | None = None,
        type_: EventType | None = None,
        category: ReportCategory | None = None,
        district: str | None = None,
        severity: Severity | None = None,
        q: str | None = None,
    ) -> list[CityEvent]:
        events = self._events.list(
            status=status,
            type_=type_,
            category=category,
            district=district,
            severity=severity,
        )
        # Drop events whose 24h (or explicitly-set) window has passed — they stay
        # in the DB (an author can still open + prolong one via `get_event`) but
        # fall off the public feed. Events with no `expires_at` (city/seed) never
        # time out. Applied in-process alongside the free-text filter below since
        # the feed is a bounded set and the criteria layer can't express the
        # "expires_at IS NULL OR expires_at > now" OR.
        now = _utcnow()
        events = [e for e in events if e.expires_at is None or e.expires_at > now]
        # Free-text search is applied in-process (the feed is a bounded set) so a
        # single query can span title/description/location without an OR-capable
        # criteria layer.
        needle = (q or "").strip().lower()
        if needle:
            events = [e for e in events if needle in self._haystack(e)]
        return events

    @staticmethod
    def _haystack(event: CityEvent) -> str:
        parts = [event.title, event.description, event.location_text, event.address]
        return " ".join(p for p in parts if p).lower()

    def get_event(self, event_id: int) -> CityEvent:
        event = self._events.get(event_id)
        if event is None:
            raise NotFoundError("zdarzenie nie istnieje")
        return event

    def prolong_event(
        self,
        event_id: int,
        requester_id: int,
        extend_by: timedelta = EVENT_DEFAULT_TTL,
    ) -> CityEvent:
        """Push an event's expiry out by `extend_by` — only the author may do so.

        The window is measured from whichever is later, now or the current
        `expires_at`, so prolonging an event that still has time left adds to it
        rather than shortening it, while a lapsed event gets a fresh window. An
        event that was explicitly marked EXPIRED is revived to ACTIVE.
        """
        event = self.get_event(event_id)
        if event.reporter_id is None or event.reporter_id != requester_id:
            raise AccessDeniedError("możesz przedłużać tylko własne zdarzenia")
        now = _utcnow()
        base = event.expires_at if event.expires_at and event.expires_at > now else now
        values: dict[str, Any] = {"expires_at": base + extend_by}
        if event.status is EventStatus.EXPIRED:
            values["status"] = EventStatus.ACTIVE.value
        return self._events.update(event_id, values) or event

    def geocode_event(self, event_id: int) -> CityEvent:
        """Resolve the event's location string to coordinates and persist them.

        Runs on the Inngest worker after an event's location is added/changed
        (see city_events_bc/inngest_functions.py::geocode_event). A no-op —
        returns the event unchanged — when the geocoder isn't configured, the
        event has no address text, or HERE finds no in-Wrocław match.
        """
        event = self.get_event(event_id)
        if self._geocoder is None or not self._geocoder.is_configured:
            return event
        query = event.address or event.location_text
        if not query:
            return event
        result = self._geocoder.geocode(query)
        if result is None:
            return event
        values: dict[str, Any] = {"lat": result.lat, "lng": result.lng}
        if result.district and not event.district:
            values["district"] = result.district
        return self._events.update(event_id, values) or event

    def create_event(
        self,
        *,
        type_: EventType,
        title: str,
        description: str,
        reporter_id: int | None = None,
        source: EventSource = EventSource.CITIZEN,
        status: EventStatus = EventStatus.ACTIVE,
        category: ReportCategory | None = None,
        severity: Severity | None = None,
        location_text: str | None = None,
        address: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        subtype: str | None = None,
        district: str | None = None,
        expires_at: datetime | None = None,
        contact_phone: str | None = None,
        image_url: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> CityEvent:
        # `confirmations` / `verified` / `resolved_at` are system-managed, so
        # they're not accepted here — the DB default (via `_normalize`) applies.
        # A resident-filed event that carries no explicit end auto-expires after
        # the default TTL so stale reports don't linger on the map forever.
        if expires_at is None:
            expires_at = _utcnow() + EVENT_DEFAULT_TTL
        return self._events.create(
            self._normalize(
                {
                    "type": type_.value,
                    "status": status.value,
                    "title": title,
                    "description": description,
                    "category": category.value if category else None,
                    "severity": severity.value if severity else None,
                    "location_text": location_text,
                    "address": address,
                    "lat": lat,
                    "lng": lng,
                    "source": source.value,
                    "reporter_id": reporter_id,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "subtype": subtype,
                    "district": district,
                    "expires_at": expires_at,
                    "contact_phone": contact_phone,
                    "image_url": image_url,
                    "details": details,
                }
            )
        )

    def ingest(self, raw_events: list[dict[str, Any]]) -> list[CityEvent]:
        """Bulk-insert events (seed / demo). Each dict is validated against the
        enums and normalised; unknown keys are dropped, missing ones defaulted."""
        rows = [self._normalize(self._coerce(e)) for e in raw_events]
        return self._events.create_many(rows)

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _coerce(e: dict[str, Any]) -> dict[str, Any]:
        """Validate/normalise a loosely-typed ingest dict into column values."""
        type_ = EventType(e["type"])
        status = EventStatus(e.get("status") or EventStatus.ACTIVE.value)
        source = EventSource(e.get("source") or EventSource.CITY.value)
        category = ReportCategory(e["category"]) if e.get("category") else None
        severity = Severity(e["severity"]) if e.get("severity") else None
        return {
            "type": type_.value,
            "status": status.value,
            "title": e["title"],
            "description": e.get("description") or "",
            "category": category.value if category else None,
            "severity": severity.value if severity else None,
            "location_text": e.get("location_text"),
            "address": e.get("address"),
            "lat": e.get("lat"),
            "lng": e.get("lng"),
            "source": source.value,
            "reporter_id": e.get("reporter_id"),
            "starts_at": e.get("starts_at"),
            "ends_at": e.get("ends_at"),
            # structured / reportable fields — permissive, seed data may set any
            "subtype": e.get("subtype"),
            "district": e.get("district"),
            "resolved_at": e.get("resolved_at"),
            "expires_at": e.get("expires_at"),
            "confirmations": e.get("confirmations"),
            "verified": e.get("verified"),
            "contact_phone": e.get("contact_phone"),
            "image_url": e.get("image_url"),
            "details": e.get("details"),
        }

    @staticmethod
    def _normalize(values: dict[str, Any]) -> dict[str, Any]:
        # Fixed key set for create_many; NOT-NULL columns get their default when
        # absent so we never insert an explicit NULL over a column default.
        return {
            col: (
                _NOT_NULL_DEFAULTS[col]
                if values.get(col) is None and col in _NOT_NULL_DEFAULTS
                else values.get(col)
            )
            for col in _COLUMNS
        }
