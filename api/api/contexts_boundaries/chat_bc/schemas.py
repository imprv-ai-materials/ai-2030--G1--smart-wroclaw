from typing import Any

from api.contexts_boundaries.city_events_bc.models import CityEvent
from pydantic import BaseModel


class ChatTurnRequest(BaseModel):
    # `text` is optional because an inline-form submission or a confirm click can
    # carry no prose — the structured `fields` / `action` are the payload then.
    text: str = ""
    conversation_id: int | None = None
    fields: dict[str, Any] | None = None
    action: str | None = None


class ChatTurnResponse(BaseModel):
    conversation_id: int
    status: str
    reply: str
    reason: str | None = None
    intent: str | None = None
    filters: dict[str, Any] | None = None
    results: list[CityEvent] | None = None
    draft: dict[str, Any] | None = None
    missing_fields: list[str] | None = None
    duplicates: list[CityEvent] | None = None
    form: list[dict[str, Any]] | None = None
    ready: bool | None = None
    created: CityEvent | None = None
    # analytics turn: the count + its per-type breakdown
    count: int | None = None
    breakdown: dict[str, int] | None = None
