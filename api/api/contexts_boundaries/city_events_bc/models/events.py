from datetime import datetime
from typing import Any

from api.contexts_boundaries.city_events_bc.models.enums import (
    EventSource,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from pydantic import BaseModel, Field


class CityEvent(BaseModel):
    """A geolocated thing happening in the city — the unit the citizen map and
    the "aktywne zdarzenia" list render.

    Deliberately broader than `IssueReport`: an event may be a citizen-reported
    fault (ISSUE), a city ALARM, a VENUE/event, or a business PROMOTION. Position
    is `(lat, lng)`; anything without coordinates simply isn't drawn on the map.
    """

    id: int
    type: EventType
    status: EventStatus
    title: str
    description: str
    category: ReportCategory | None = None
    severity: Severity | None = None
    location_text: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    source: EventSource = EventSource.CITY
    reporter_id: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # Structured / reportable fields (migration 0005). `subtype` refines within a
    # `type`; `details` holds the per-type long tail (animal_species, utility, …).
    subtype: str | None = None
    district: str | None = None
    resolved_at: datetime | None = None
    expires_at: datetime | None = None
    confirmations: int = 0
    verified: bool = False
    contact_phone: str | None = None
    image_url: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CityEvent":
        return cls(
            id=data["id"],
            type=EventType(data["type"]),
            status=EventStatus(data["status"]),
            title=data["title"],
            description=data["description"],
            category=ReportCategory(data["category"]) if data.get("category") else None,
            severity=Severity(data["severity"]) if data.get("severity") else None,
            location_text=data.get("location_text"),
            address=data.get("address"),
            lat=data.get("lat"),
            lng=data.get("lng"),
            source=EventSource(data.get("source") or EventSource.CITY.value),
            reporter_id=data.get("reporter_id"),
            starts_at=data.get("starts_at"),
            ends_at=data.get("ends_at"),
            subtype=data.get("subtype"),
            district=data.get("district"),
            resolved_at=data.get("resolved_at"),
            expires_at=data.get("expires_at"),
            confirmations=data.get("confirmations") or 0,
            verified=bool(data.get("verified")),
            contact_phone=data.get("contact_phone"),
            image_url=data.get("image_url"),
            # psycopg parses JSONB to a Python object already; guard against NULL.
            details=data.get("details") or {},
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
