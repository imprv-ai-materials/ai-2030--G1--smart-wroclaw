"""EventsService against a real Postgres — the user map feed.

Shows the integration conventions: `BaseIntegrationTestCase`, state built with
the `db_agg_factory` fluent builder, `parameterized.expand` cases even for
DB-backed tests, and GIVEN/WHEN/THEN.
"""

from datetime import datetime, timedelta, timezone

import pytest
from api.contexts_boundaries.city_events_bc.models import EventSource, EventStatus, EventType
from api.contexts_boundaries.city_events_bc.services.events import EVENT_DEFAULT_TTL
from api.shared.exceptions import AccessDeniedError, NotFoundError
from parameterized import param, parameterized
from tests import BaseIntegrationTestCase


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class TestEventsServiceListEvents(BaseIntegrationTestCase):
    def _seed_mixed_feed(self) -> None:
        # 2 active, 2 issues, exactly 1 active-issue.
        (
            self.db_agg_factory.create()
            .create_city_event("active_issue", type=EventType.ISSUE, status=EventStatus.ACTIVE)
            .create_city_event("resolved_issue", type=EventType.ISSUE, status=EventStatus.RESOLVED)
            .create_city_event("active_alarm", type=EventType.ALARM, status=EventStatus.ACTIVE)
        )

    @parameterized.expand(
        [
            param("status only → both ACTIVE", status=EventStatus.ACTIVE, type_=None, expected=2),
            param("type only → both ISSUE", status=None, type_=EventType.ISSUE, expected=2),
            param(
                "status AND type → the one active issue",
                status=EventStatus.ACTIVE,
                type_=EventType.ISSUE,
                expected=1,
            ),
            param("no filter → the whole feed", status=None, type_=None, expected=3),
        ]
    )
    def test_list_events__filters(self, _, status, type_, expected) -> None:
        # GIVEN a feed of three events
        self._seed_mixed_feed()

        # WHEN the feed is listed with the given filters
        events = self.events_service.list_events(status=status, type_=type_)

        # THEN only the matching events are returned
        assert len(events) == expected


class TestEventsServiceExpiry(BaseIntegrationTestCase):
    def test_list_events__hides_time_expired(self) -> None:
        # GIVEN a live event, an expired one, and one with no expiry (city/seed)
        (
            self.db_agg_factory.create()
            .create_city_event("live", title="Żywe", expires_at=_now() + timedelta(hours=1))
            .create_city_event("stale", title="Wygasłe", expires_at=_now() - timedelta(minutes=1))
            .create_city_event("evergreen", title="Bezterminowe", expires_at=None)
        )

        # WHEN the public feed is listed
        titles = {e.title for e in self.events_service.list_events()}

        # THEN the expired one is dropped; the live + evergreen ones remain
        assert titles == {"Żywe", "Bezterminowe"}

    def test_get_event__still_returns_expired(self) -> None:
        # GIVEN an event past its expiry (so it's off the feed)
        agg = self.db_agg_factory.create().create_city_event(
            "stale", expires_at=_now() - timedelta(hours=1)
        )
        stale = agg.get("city_events", "stale")

        # WHEN it is fetched directly (e.g. the author opening it to prolong)
        # THEN it is still returned — only the feed hides it
        assert self.events_service.get_event(stale["id"]).id == stale["id"]

    def test_create_event__defaults_expiry_to_ttl(self) -> None:
        # GIVEN a resident
        agg = self.db_agg_factory.create().create_user("resident")
        resident = agg.get("users", "resident")

        # WHEN they file an event without an explicit expiry
        before = _now()
        event = self.events_service.create_event(
            type_=EventType.ISSUE,
            title="Rozlana farba na chodniku",
            description="Ktoś rozlał farbę",
            reporter_id=resident["id"],
        )

        # THEN it auto-expires roughly one TTL from now
        assert event.expires_at is not None
        assert before + EVENT_DEFAULT_TTL - timedelta(minutes=1) <= event.expires_at


class TestEventsServiceProlong(BaseIntegrationTestCase):
    def _authored_event(self, **kwargs) -> tuple[dict, dict]:
        agg = (
            self.db_agg_factory.create()
            .create_user("author")
            .create_city_event(
                "event", reporter_label="author", source=EventSource.USER, **kwargs
            )
        )
        return agg.get("users", "author"), agg.get("city_events", "event")

    def test_prolong__author__pushes_expiry_out(self) -> None:
        # GIVEN an author's event that still has a little time left
        soon = _now() + timedelta(hours=1)
        author, event = self._authored_event(expires_at=soon)

        # WHEN the author prolongs it
        updated = self.events_service.prolong_event(event["id"], requester_id=author["id"])

        # THEN a fresh TTL is added on top of the remaining time
        assert updated.expires_at is not None
        assert updated.expires_at > soon + EVENT_DEFAULT_TTL - timedelta(minutes=1)

    def test_prolong__revives_a_lapsed_event(self) -> None:
        # GIVEN an author's event that already lapsed
        author, event = self._authored_event(expires_at=_now() - timedelta(hours=5))

        # WHEN the author prolongs it
        updated = self.events_service.prolong_event(event["id"], requester_id=author["id"])

        # THEN it is visible again (a full TTL from now, not from the old expiry)
        assert updated.expires_at is not None
        assert updated.expires_at > _now() + EVENT_DEFAULT_TTL - timedelta(minutes=1)

    def test_prolong__non_author__access_denied(self) -> None:
        # GIVEN an event authored by someone else
        _, event = self._authored_event(expires_at=_now() + timedelta(hours=1))
        other = self.db_agg_factory.create().create_user("intruder").get(
            "users", "intruder"
        )

        # WHEN a different resident tries to prolong it
        # THEN it is refused
        with pytest.raises(AccessDeniedError):
            self.events_service.prolong_event(event["id"], requester_id=other["id"])


class TestEventsServiceGetEvent(BaseIntegrationTestCase):
    def test_get_event__existing__round_trips(self) -> None:
        # GIVEN a persisted event
        agg = self.db_agg_factory.create().create_city_event("event", title="Awaria wodociągu")
        created = agg.get("city_events", "event")

        # WHEN it is fetched by id
        event = self.events_service.get_event(created["id"])

        # THEN the domain object matches what was stored
        assert event.id == created["id"]
        assert event.title == "Awaria wodociągu"

    def test_get_event__missing__raises_not_found(self) -> None:
        # GIVEN an empty feed
        # WHEN / THEN fetching an unknown id surfaces the domain NotFoundError
        with pytest.raises(NotFoundError):
            self.events_service.get_event(999_999)


class TestEventsServiceCreateEvent(BaseIntegrationTestCase):
    def test_create_event__user_report__persists_and_attributes(self) -> None:
        # GIVEN a resident
        agg = self.db_agg_factory.create().create_user("resident")
        resident = agg.get("users", "resident")

        # WHEN they file an event
        event = self.events_service.create_event(
            type_=EventType.ISSUE,
            title="Przewrócone drzewo",
            description="Drzewo blokuje chodnik po wichurze",
            reporter_id=resident["id"],
        )

        # THEN it is stored, attributed to them, and visible in the feed
        assert event.id is not None
        assert event.reporter_id == resident["id"]
        assert self.events_service.get_event(event.id).title == "Przewrócone drzewo"
