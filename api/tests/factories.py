"""Test data factories — ported from imprv-api's `tests/factories.py`.

Three flavours, same "kwargs default to a faker value" convention throughout:

* **`DBFactory`** — persists a row via `DBClient` and returns the inserted dict.
  One `<entity>_db(...)` method per table. `clear()` truncates every table in
  dependency order (the integration DB-isolation workhorse).
* **`DomainFactory`** — builds in-memory pydantic domain models (no DB). Use in
  unit tests.
* **`DBAggregatesFactory` / `DynamicalAggregator`** — the "agg" factory: a
  fluent, label-keyed builder that composes `DBFactory` calls and resolves
  cross-entity references by label. This is the primary way integration tests
  set up a graph of related rows:

      agg = (
          db_agg_factory.create()
          .create_user("resident", email_confirmed=True)
          .create_city_event("event", reporter_label="resident")
      )
      event = agg.get("city_events", "event")
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Self

from api.adapters.db import DBClient
from api.contexts_boundaries.auth_bc.models import TokenKind, User
from api.contexts_boundaries.auth_bc.repositories.tables import (
    auth_tokens_table,
    users_table,
)
from api.contexts_boundaries.auth_bc.security import generate_token, hash_password
from api.contexts_boundaries.chat_bc.repositories.tables import (
    chat_conversations_table,
    chat_messages_table,
)
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventSource,
    EventStatus,
    EventType,
    ReportCategory,
    Severity,
)
from api.contexts_boundaries.city_events_bc.repositories.tables import city_events_table
from faker import Faker

# The seeded system "City" account (migration 0003) — events without a real
# reporter are owned by it (city_events.reporter_id is a NOT NULL FK).
SYSTEM_USER_ID = 1


def _val(value: Any) -> Any:
    """Enum -> its value; everything else unchanged (columns store strings)."""
    return value.value if hasattr(value, "value") else value


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class DBFactory:
    """Persists rows to Postgres and returns the inserted dict."""

    def __init__(self, db_client: DBClient) -> None:
        self.faker = Faker("pl_PL")
        self.db_client = db_client

    # -- auth_bc ----------------------------------------------------------- #
    def user_db(
        self,
        email: str | None = None,
        password: str = "haslo123",
        password_hash: str | None = None,
        email_confirmed: bool = True,
        phone: str | None = None,
    ) -> dict:
        return self.db_client.create_one(
            users_table,
            values={
                "email": email or self.faker.unique.email(),
                "password_hash": password_hash or hash_password(password, ""),
                "email_confirmed": email_confirmed,
                "phone": phone,
            },
        )

    def auth_token_db(
        self,
        user_id: int,
        kind: TokenKind = TokenKind.CONFIRM_EMAIL,
        token_hash: str | None = None,
        expires_at: datetime | None = None,
        used_at: datetime | None = None,
    ) -> dict:
        return self.db_client.create_one(
            auth_tokens_table,
            values={
                "user_id": user_id,
                "kind": _val(kind),
                "token_hash": token_hash or generate_token()[1],
                "expires_at": expires_at or (_now() + timedelta(hours=48)),
                "used_at": used_at,
            },
        )

    # -- city_events_bc: the map feed ------------------------------------- #
    def city_event_db(
        self,
        type: EventType = EventType.ISSUE,
        status: EventStatus = EventStatus.ACTIVE,
        title: str | None = None,
        description: str | None = None,
        category: ReportCategory | None = None,
        severity: Severity | None = None,
        location_text: str | None = None,
        address: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        source: EventSource = EventSource.CITY,
        reporter_id: int | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> dict:
        return self.db_client.create_one(
            city_events_table,
            values={
                "type": _val(type),
                "status": _val(status),
                "title": title or self.faker.sentence(nb_words=5),
                "description": description or self.faker.paragraph(nb_sentences=2),
                "category": _val(category),
                "severity": _val(severity),
                "location_text": location_text,
                "address": address,
                "lat": lat,
                "lng": lng,
                "source": _val(source),
                # NOT NULL FK → users(id); fall back to the system "City" account.
                "reporter_id": reporter_id if reporter_id is not None else SYSTEM_USER_ID,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "expires_at": expires_at,
            },
        )

    # -- isolation --------------------------------------------------------- #
    def clear(self) -> None:
        """DELETE FROM every table, children before parents. Called at the start
        of each integration test so cases never leak state into one another.

        The seeded system user (id 1) is preserved so city_events' NOT NULL FK
        stays satisfiable."""
        for table in (
            chat_messages_table,
            chat_conversations_table,
            city_events_table,
            auth_tokens_table,
        ):
            self.db_client.delete_many(table, {})
        # Keep the system "City" account (id 1); drop every real user.
        self.db_client.delete_many(users_table, {"id__gte": SYSTEM_USER_ID + 1})


class DomainFactory:
    """Builds in-memory pydantic domain models (no DB). For unit tests."""

    def __init__(self) -> None:
        self.faker = Faker("pl_PL")

    def user(
        self,
        id: int | None = None,
        email: str | None = None,
        password_hash: str = "x" * 60,
        email_confirmed: bool = True,
        phone: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> User:
        now = _now()
        return User(
            id=id or self.faker.random_int(1, 1_000_000),
            email=email or self.faker.email(),
            password_hash=password_hash,
            email_confirmed=email_confirmed,
            phone=phone,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )

    def city_event(
        self,
        id: int | None = None,
        type: EventType = EventType.ISSUE,
        status: EventStatus = EventStatus.ACTIVE,
        title: str | None = None,
        description: str | None = None,
        category: ReportCategory | None = None,
        severity: Severity | None = None,
        source: EventSource = EventSource.CITY,
        reporter_id: int = SYSTEM_USER_ID,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> CityEvent:
        now = _now()
        return CityEvent(
            id=id or self.faker.random_int(1, 1_000_000),
            type=type,
            status=status,
            title=title or self.faker.sentence(nb_words=5),
            description=description or self.faker.paragraph(nb_sentences=2),
            category=category,
            severity=severity,
            source=source,
            reporter_id=reporter_id,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )


class DBAggregatesFactory:
    """Hands out fresh `DynamicalAggregator`s (one per `create()` call)."""

    def __init__(self, db_factory: DBFactory, db_client: DBClient) -> None:
        self.db_factory = db_factory
        self.db_client = db_client

    def create(self) -> "DynamicalAggregator":
        return DynamicalAggregator(self.db_factory, self.db_client)


class DynamicalAggregator:
    """Fluent, label-keyed builder composing `DBFactory` calls.

    Each `create_<thing>(label, ...)` (1) resolves referenced parents by label
    (or the most-recently-created one), (2) persists the row, (3) stores it under
    `(group, label)`, and (4) returns `self` for chaining. Retrieve rows with
    `.get(group, label)` or `.get_latest(group)`.
    """

    def __init__(self, db_factory: DBFactory, db_client: DBClient) -> None:
        self.db_factory = db_factory
        self.db_client = db_client
        self._entities: dict[str, dict[str, dict]] = {}
        self._active_group: str | None = None
        self._active_labels: dict[str, str] = {}

    # -- builders ---------------------------------------------------------- #
    def create_user(self, label: str, **kwargs: Any) -> Self:
        self._add_entity("users", label, self.db_factory.user_db(**kwargs))
        return self

    def create_auth_token(self, label: str, user_label: str | None = None, **kwargs: Any) -> Self:
        user = self._resolve("users", user_label)
        self._add_entity("auth_tokens", label, self.db_factory.auth_token_db(user_id=user["id"], **kwargs))
        return self

    def create_city_event(self, label: str, reporter_label: str | None = None, **kwargs: Any) -> Self:
        reporter_id = None
        if reporter_label is not None:
            reporter_id = self._get_entity("users", reporter_label)["id"]
        self._add_entity("city_events", label, self.db_factory.city_event_db(reporter_id=reporter_id, **kwargs))
        return self

    # -- accessors --------------------------------------------------------- #
    def get(self, group: str, label: str) -> dict:
        return self._entities[group][label]

    def get_latest(self, group: str | None = None) -> dict:
        if group is None:
            group = self._active_group  # type: ignore[assignment]
        return self._entities[group][self._active_labels[group]]

    # -- internals --------------------------------------------------------- #
    def _resolve(self, group: str, label: str | None) -> dict:
        return self._get_entity(group, label) if label else self.get_latest(group)

    def _get_entity(self, group: str, label: str) -> dict:
        return self._entities[group][label]

    def _add_entity(self, group: str, label: str, entity: dict) -> None:
        if not label.isidentifier():
            raise ValueError(f"label {label!r} must be a valid python identifier")
        self._active_group = group
        self._active_labels[group] = label
        self._entities.setdefault(group, {})[label] = entity
