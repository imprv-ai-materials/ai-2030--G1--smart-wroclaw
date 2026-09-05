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
          .create_citizen("resident", email_confirmed=True)
          .create_issue_report("report", citizen_label="resident")
          .create_report_review("review", report_label="report")
      )
      report = agg.get("issue_reports", "report")
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Self

from api.adapters.db import DBClient
from api.contexts_boundaries.assistant_bc.repositories.tables import (
    conversations_table,
    messages_table,
)
from api.contexts_boundaries.auth_bc.models import TokenKind
from api.contexts_boundaries.auth_bc.models.users import Citizen
from api.contexts_boundaries.auth_bc.repositories.tables import (
    auth_tokens_table,
    citizens_table,
)
from api.contexts_boundaries.auth_bc.security import generate_token, hash_password
from api.contexts_boundaries.city_events_bc.models import (
    CityEvent,
    EventSource,
    EventStatus,
    EventType,
    IssueReport,
    ReportCategory,
    ReportStatus,
    ReviewDecision,
    Severity,
    TriageResult,
)
from api.contexts_boundaries.city_events_bc.repositories.tables import (
    city_events_table,
    issue_reports_table,
    report_reviews_table,
)
from faker import Faker

# assistant_runs / run_events are only cleared, never built here yet.
from api.contexts_boundaries.assistant_bc.repositories.tables import (  # isort: skip
    assistant_runs_table,
    run_events_table,
)


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
    def citizen_db(
        self,
        email: str | None = None,
        password: str = "haslo123",
        password_hash: str | None = None,
        email_confirmed: bool = True,
        phone: str | None = None,
    ) -> dict:
        return self.db_client.create_one(
            citizens_table,
            values={
                "email": email or self.faker.unique.email(),
                "password_hash": password_hash or hash_password(password, ""),
                "email_confirmed": email_confirmed,
                "phone": phone,
            },
        )

    def auth_token_db(
        self,
        citizen_id: int,
        kind: TokenKind = TokenKind.CONFIRM_EMAIL,
        token_hash: str | None = None,
        expires_at: datetime | None = None,
        used_at: datetime | None = None,
    ) -> dict:
        return self.db_client.create_one(
            auth_tokens_table,
            values={
                "citizen_id": citizen_id,
                "kind": _val(kind),
                "token_hash": token_hash or generate_token()[1],
                "expires_at": expires_at or (_now() + timedelta(hours=48)),
                "used_at": used_at,
            },
        )

    # -- city_events_bc: issue reports (HITL) ------------------------------ #
    def issue_report_db(
        self,
        citizen_id: int,
        title: str | None = None,
        description: str | None = None,
        category: ReportCategory | None = None,
        location_text: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        status: ReportStatus = ReportStatus.SUBMITTED,
        severity: Severity | None = None,
        department: str | None = None,
        triage: dict | None = None,
        public_response: str | None = None,
        reviewed_by: str | None = None,
        reviewed_at: datetime | None = None,
    ) -> dict:
        return self.db_client.create_one(
            issue_reports_table,
            values={
                "citizen_id": citizen_id,
                "title": title or self.faker.sentence(nb_words=5),
                "description": description or self.faker.paragraph(nb_sentences=2),
                "category": _val(category),
                "location_text": location_text,
                "lat": lat,
                "lng": lng,
                "status": _val(status),
                "severity": _val(severity),
                "department": department,
                "triage": triage,
                "public_response": public_response,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
            },
        )

    def report_review_db(
        self,
        report_id: int,
        specialist_id: str = "specialist-1",
        decision: ReviewDecision = ReviewDecision.APPROVE,
        edited_category: ReportCategory | None = None,
        edited_severity: Severity | None = None,
        edited_department: str | None = None,
        public_response: str | None = None,
        comment: str = "",
    ) -> dict:
        return self.db_client.create_one(
            report_reviews_table,
            values={
                "report_id": report_id,
                "specialist_id": specialist_id,
                "decision": _val(decision),
                "edited_category": _val(edited_category),
                "edited_severity": _val(edited_severity),
                "edited_department": edited_department,
                "public_response": public_response,
                "comment": comment,
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
                "reporter_id": reporter_id,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "expires_at": expires_at,
            },
        )

    # -- assistant_bc ------------------------------------------------------ #
    def conversation_db(self, citizen_id: int, title: str | None = None) -> dict:
        return self.db_client.create_one(
            conversations_table,
            values={"citizen_id": citizen_id, "title": title},
        )

    def message_db(
        self,
        conversation_id: int,
        role: str = "USER",
        content: str | None = None,
        run_id: int | None = None,
    ) -> dict:
        return self.db_client.create_one(
            messages_table,
            values={
                "conversation_id": conversation_id,
                "role": role,
                "content": content if content is not None else self.faker.sentence(),
                "run_id": run_id,
            },
        )

    # -- isolation --------------------------------------------------------- #
    def clear(self) -> None:
        """DELETE FROM every table, children before parents. Called at the start
        of each integration test so cases never leak state into one another."""
        for table in (
            report_reviews_table,
            issue_reports_table,
            run_events_table,
            assistant_runs_table,
            messages_table,
            conversations_table,
            city_events_table,
            auth_tokens_table,
            citizens_table,
        ):
            self.db_client.delete_many(table, {})


class DomainFactory:
    """Builds in-memory pydantic domain models (no DB). For unit tests."""

    def __init__(self) -> None:
        self.faker = Faker("pl_PL")

    def citizen(
        self,
        id: int | None = None,
        email: str | None = None,
        password_hash: str = "x" * 60,
        email_confirmed: bool = True,
        phone: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> Citizen:
        now = _now()
        return Citizen(
            id=id or self.faker.random_int(1, 1_000_000),
            email=email or self.faker.email(),
            password_hash=password_hash,
            email_confirmed=email_confirmed,
            phone=phone,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )

    def triage_result(
        self,
        category: ReportCategory = ReportCategory.OTHER,
        severity: Severity = Severity.MEDIUM,
        department: str = "",
        summary: str | None = None,
        suggested_response: str | None = None,
        is_duplicate: bool = False,
        confidence: float = 0.5,
    ) -> TriageResult:
        return TriageResult(
            category=category,
            severity=severity,
            department=department,
            summary=summary if summary is not None else self.faker.sentence(),
            suggested_response=suggested_response if suggested_response is not None else self.faker.sentence(),
            is_duplicate=is_duplicate,
            confidence=confidence,
        )

    def issue_report(
        self,
        id: int | None = None,
        citizen_id: int | None = None,
        title: str | None = None,
        description: str | None = None,
        category: ReportCategory | None = None,
        location_text: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        status: ReportStatus = ReportStatus.SUBMITTED,
        severity: Severity | None = None,
        department: str | None = None,
        triage: TriageResult | None = None,
        public_response: str | None = None,
        reviewed_by: str | None = None,
        reviewed_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> IssueReport:
        now = _now()
        return IssueReport(
            id=id or self.faker.random_int(1, 1_000_000),
            citizen_id=citizen_id or self.faker.random_int(1, 1_000_000),
            title=title or self.faker.sentence(nb_words=5),
            description=description or self.faker.paragraph(nb_sentences=2),
            category=category,
            location_text=location_text,
            lat=lat,
            lng=lng,
            status=status,
            severity=severity,
            department=department,
            triage=triage,
            public_response=public_response,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
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
        reporter_id: int | None = None,
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
    def create_citizen(self, label: str, **kwargs: Any) -> Self:
        self._add_entity("citizens", label, self.db_factory.citizen_db(**kwargs))
        return self

    def create_auth_token(self, label: str, citizen_label: str | None = None, **kwargs: Any) -> Self:
        citizen = self._resolve("citizens", citizen_label)
        self._add_entity("auth_tokens", label, self.db_factory.auth_token_db(citizen_id=citizen["id"], **kwargs))
        return self

    def create_issue_report(self, label: str, citizen_label: str | None = None, **kwargs: Any) -> Self:
        citizen = self._resolve("citizens", citizen_label)
        self._add_entity(
            "issue_reports",
            label,
            self.db_factory.issue_report_db(citizen_id=citizen["id"], **kwargs),
        )
        return self

    def create_report_review(self, label: str, report_label: str | None = None, **kwargs: Any) -> Self:
        report = self._resolve("issue_reports", report_label)
        self._add_entity(
            "report_reviews",
            label,
            self.db_factory.report_review_db(report_id=report["id"], **kwargs),
        )
        return self

    def create_city_event(self, label: str, reporter_label: str | None = None, **kwargs: Any) -> Self:
        reporter_id = None
        if reporter_label is not None:
            reporter_id = self._get_entity("citizens", reporter_label)["id"]
        self._add_entity("city_events", label, self.db_factory.city_event_db(reporter_id=reporter_id, **kwargs))
        return self

    def create_conversation(self, label: str, citizen_label: str | None = None, **kwargs: Any) -> Self:
        citizen = self._resolve("citizens", citizen_label)
        self._add_entity(
            "conversations",
            label,
            self.db_factory.conversation_db(citizen_id=citizen["id"], **kwargs),
        )
        return self

    def create_message(self, label: str, conversation_label: str | None = None, **kwargs: Any) -> Self:
        conversation = self._resolve("conversations", conversation_label)
        self._add_entity(
            "messages",
            label,
            self.db_factory.message_db(conversation_id=conversation["id"], **kwargs),
        )
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
