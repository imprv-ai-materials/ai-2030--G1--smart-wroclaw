import abc
from typing import Any

from api.adapters.db import DBClient
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from api.contexts_boundaries.city_events_bc.repositories.tables import city_events_table


class AbstractEventsRepository(abc.ABC):
    @abc.abstractmethod
    def create(self, values: dict[str, Any]) -> CityEvent: ...

    @abc.abstractmethod
    def create_many(self, rows: list[dict[str, Any]]) -> list[CityEvent]: ...

    @abc.abstractmethod
    def get(self, event_id: int) -> CityEvent | None: ...

    @abc.abstractmethod
    def list(
        self,
        status: EventStatus | None = None,
        type_: EventType | None = None,
        category: ReportCategory | None = None,
        district: str | None = None,
        severity: Severity | None = None,
        limit: int = 500,
    ) -> list[CityEvent]: ...

    @abc.abstractmethod
    def update(self, event_id: int, values: dict[str, Any]) -> CityEvent | None: ...


class EventsRepository(AbstractEventsRepository):
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    def create(self, values: dict[str, Any]) -> CityEvent:
        row = self._db.create_one(city_events_table, values=values)
        return CityEvent.from_dict(row)

    def create_many(self, rows: list[dict[str, Any]]) -> list[CityEvent]:
        if not rows:
            return []
        created = self._db.create_many(city_events_table, values=rows)
        return [CityEvent.from_dict(r) for r in created]

    def get(self, event_id: int) -> CityEvent | None:
        row = self._db.get_one(city_events_table, {"id": event_id})
        return CityEvent.from_dict(row) if row else None

    def list(
        self,
        status: EventStatus | None = None,
        type_: EventType | None = None,
        category: ReportCategory | None = None,
        district: str | None = None,
        severity: Severity | None = None,
        limit: int = 500,
    ) -> list[CityEvent]:
        criteria: dict[str, Any] = {}
        if status is not None:
            criteria["status"] = status.value
        if type_ is not None:
            criteria["type"] = type_.value
        if category is not None:
            criteria["category"] = category.value
        if severity is not None:
            criteria["severity"] = severity.value
        if district:
            criteria["district__ilike"] = f"%{district}%"
        rows = self._db.get_many(
            city_events_table, criteria=criteria, order_by="-created_at", limit=limit
        )
        return [CityEvent.from_dict(r) for r in rows]

    def update(self, event_id: int, values: dict[str, Any]) -> CityEvent | None:
        self._db.update_one(city_events_table, {"id": event_id}, values)
        return self.get(event_id)
