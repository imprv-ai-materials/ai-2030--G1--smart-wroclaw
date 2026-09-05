from datetime import datetime
from typing import Any

from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventSource,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from pydantic import BaseModel, Field


class EventCreateRequest(BaseModel):
    """A resident filing an event ("zgłoś awarię / zgłoś zdarzenie")."""

    type: EventType = EventType.ISSUE
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    category: ReportCategory | None = None
    severity: Severity | None = None
    location_text: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # Structured extras a resident may attach (e.g. a lost dog's contact phone,
    # its species in `details`). `confirmations` / `verified` stay system-only.
    subtype: str | None = None
    district: str | None = None
    expires_at: datetime | None = None
    contact_phone: str | None = None
    image_url: str | None = None
    details: dict[str, Any] | None = None


class EventIngestItem(BaseModel):
    """One row for the bulk seed/ingest path — permissive on purpose."""

    type: EventType
    title: str
    description: str = ""
    status: EventStatus = EventStatus.ACTIVE
    source: EventSource = EventSource.CITY
    category: ReportCategory | None = None
    severity: Severity | None = None
    location_text: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # structured / reportable fields — seed data may set any of these
    subtype: str | None = None
    district: str | None = None
    resolved_at: datetime | None = None
    expires_at: datetime | None = None
    confirmations: int | None = None
    verified: bool | None = None
    contact_phone: str | None = None
    image_url: str | None = None
    details: dict[str, Any] | None = None


class EventIngestRequest(BaseModel):
    events: list[EventIngestItem]


class EventListResponse(BaseModel):
    events: list[CityEvent]
