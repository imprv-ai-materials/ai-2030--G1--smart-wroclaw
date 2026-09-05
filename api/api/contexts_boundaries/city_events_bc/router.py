"""Public user event feed + the authenticated "file an event" write.

    GET  /events?status=&type=   the map / list feed (public)
    GET  /events/{id}            one event's dedicated page (public)
    POST /events                 file an event (logged-in + confirmed email)
    POST /events/{id}/prolong    extend your own event's window (author-only)

Bulk seeding is a dev/CLI concern now (`pypyr seed_events` → EventsService.ingest),
so there is no HTTP ingest endpoint.
"""

import inngest
from api.bootstrap import Bootstrap
from api.contexts_boundaries.auth_bc import get_bootstrap_dep, require_confirmed_user
from api.contexts_boundaries.auth_bc.models import User
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventSource,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from api.contexts_boundaries.city_events_bc.schemas import EventCreateRequest, EventListResponse
from api.inngest_app import EVENT_EVENT_GEOCODE, inngest_client
from api.shared.exceptions import AccessDeniedError, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, status

events_router = APIRouter(prefix="/events", tags=["events"])


@events_router.get("", response_model=EventListResponse)
def list_events(
    status: EventStatus | None = None,
    type: EventType | None = None,
    category: ReportCategory | None = None,
    district: str | None = None,
    severity: Severity | None = None,
    q: str | None = None,
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> EventListResponse:
    return EventListResponse(
        events=bootstrap.events_service.list_events(
            status=status,
            type_=type,
            category=category,
            district=district,
            severity=severity,
            q=q,
        )
    )


@events_router.get("/{event_id}", response_model=CityEvent)
def get_event(
    event_id: int,
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> CityEvent:
    try:
        return bootstrap.events_service.get_event(event_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@events_router.post("/{event_id}/prolong", response_model=CityEvent)
def prolong_event(
    event_id: int,
    current: User = Depends(require_confirmed_user),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> CityEvent:
    """Extend an event's visibility window by another 24h. Author-only: the map
    marks your own events, and only you can keep them alive past their expiry."""
    try:
        return bootstrap.events_service.prolong_event(event_id, requester_id=current.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@events_router.post("", response_model=CityEvent, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreateRequest,
    current: User = Depends(require_confirmed_user),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> CityEvent:
    event = bootstrap.events_service.create_event(
        type_=body.type,
        title=body.title,
        description=body.description,
        reporter_id=current.id,
        source=EventSource.USER,
        category=body.category,
        severity=body.severity,
        location_text=body.location_text,
        address=body.address,
        lat=body.lat,
        lng=body.lng,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        subtype=body.subtype,
        district=body.district,
        expires_at=body.expires_at,
        contact_phone=body.contact_phone,
        image_url=body.image_url,
        details=body.details,
    )
    # Enrich coordinates from the location string in the background (HERE).
    if event.location_text or event.address:
        await inngest_client.send(
            inngest.Event(name=EVENT_EVENT_GEOCODE, data={"event_id": event.id})
        )
    return event
