"""The /api/v1/events HTTP surface, driven end-to-end with the TestClient.

Covers the auth modes the router exposes: a public GET feed and an authenticated
(JWT + confirmed-email) user write / prolong.
"""

from datetime import datetime, timedelta, timezone

from api.contexts_boundaries.city_events_bc.models import EventSource, EventStatus
from tests import BaseIntegrationTestCase
from tests._helpers.jwt import auth_headers


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class TestEventsFeedApi(BaseIntegrationTestCase):
    def test_get_events__public__returns_active_feed(self) -> None:
        # GIVEN two active events on the map
        (
            self.db_agg_factory.create()
            .create_city_event("a", status=EventStatus.ACTIVE)
            .create_city_event("b", status=EventStatus.ACTIVE)
        )

        # WHEN an anonymous visitor hits the public feed
        response = self.client.get("/api/v1/events", params={"status": "ACTIVE"})

        # THEN both events come back, no auth required
        assert response.status_code == 200
        assert len(response.json()["events"]) == 2


class TestCreateEventApi(BaseIntegrationTestCase):
    def _resident(self, *, email_confirmed: bool) -> dict:
        agg = self.db_agg_factory.create().create_user("resident", email_confirmed=email_confirmed)
        return agg.get("users", "resident")

    def test_post_event__confirmed_user__201_and_attributed(self) -> None:
        # GIVEN a logged-in, email-confirmed resident
        resident = self._resident(email_confirmed=True)
        headers = auth_headers(resident["id"], resident["email"], self.config)

        # WHEN they file an event
        response = self.client.post(
            "/api/v1/events",
            headers=headers,
            json={
                "type": "ISSUE",
                "title": "Zepsuta latarnia",
                "description": "Nie świeci od tygodnia",
            },
        )

        # THEN it is created, attributed to them, sourced as a user report
        assert response.status_code == 201
        body = response.json()
        assert body["reporter_id"] == resident["id"]
        assert body["source"] == "USER"

    def test_post_event__unconfirmed_email__403(self) -> None:
        # GIVEN a resident who hasn't confirmed their email
        resident = self._resident(email_confirmed=False)
        headers = auth_headers(resident["id"], resident["email"], self.config)

        # WHEN they try to file an event
        response = self.client.post(
            "/api/v1/events",
            headers=headers,
            json={"type": "ISSUE", "title": "Cokolwiek", "description": "Opis zgłoszenia"},
        )

        # THEN the confirmed-email gate rejects them
        assert response.status_code == 403

    def test_post_event__no_bearer_token__401(self) -> None:
        # GIVEN no Authorization header
        # WHEN posting an event
        response = self.client.post(
            "/api/v1/events",
            json={"type": "ISSUE", "title": "Cokolwiek", "description": "Opis zgłoszenia"},
        )

        # THEN HTTPBearer(auto_error=True) rejects a missing credential as 401
        assert response.status_code == 401


class TestProlongEventApi(BaseIntegrationTestCase):
    def test_prolong__author__200_and_expiry_moves_out(self) -> None:
        # GIVEN a confirmed resident with an event about to lapse
        agg = (
            self.db_agg_factory.create()
            .create_user("author", email_confirmed=True)
            .create_city_event(
                "event",
                reporter_label="author",
                source=EventSource.USER,
                expires_at=_now() + timedelta(minutes=30),
            )
        )
        author = agg.get("users", "author")
        event = agg.get("city_events", "event")
        headers = auth_headers(author["id"], author["email"], self.config)

        # WHEN the author prolongs it
        response = self.client.post(f"/api/v1/events/{event['id']}/prolong", headers=headers)

        # THEN it succeeds and the expiry is pushed well into the future
        assert response.status_code == 200
        new_expiry = datetime.fromisoformat(response.json()["expires_at"])
        assert new_expiry > _now() + timedelta(hours=12)

    def test_prolong__not_the_author__403(self) -> None:
        # GIVEN an event authored by one resident
        agg = (
            self.db_agg_factory.create()
            .create_user("author")
            .create_user("intruder", email_confirmed=True)
            .create_city_event(
                "event", reporter_label="author", source=EventSource.USER
            )
        )
        intruder = agg.get("users", "intruder")
        event = agg.get("city_events", "event")
        headers = auth_headers(intruder["id"], intruder["email"], self.config)

        # WHEN a different resident tries to prolong it
        response = self.client.post(f"/api/v1/events/{event['id']}/prolong", headers=headers)

        # THEN the author-only gate rejects them
        assert response.status_code == 403

    def test_prolong__missing_event__404(self) -> None:
        # GIVEN a confirmed resident
        agg = self.db_agg_factory.create().create_user("resident", email_confirmed=True)
        resident = agg.get("users", "resident")
        headers = auth_headers(resident["id"], resident["email"], self.config)

        # WHEN they prolong an event that doesn't exist
        response = self.client.post("/api/v1/events/999999/prolong", headers=headers)

        # THEN it 404s
        assert response.status_code == 404
