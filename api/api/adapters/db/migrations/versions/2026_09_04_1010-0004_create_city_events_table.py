"""create the geolocated city_events table

Revision ID: 0004_city_events
Revises: 0003_auth
Create Date: 2026-09-04 10:10:00.000000

`city_events` is the user-map feed: geolocated things of a `type`
(ISSUE / ALARM / VENUE / PROMOTION) with a `status`, a `source` (who filed it),
an owning `reporter_id` (NOT NULL FK → users), and optional `(lat, lng)`. It
powers the map and the "aktywne zdarzenia" list on the resident home screen.
"""

from api.adapters.db.migrations.versions import execute

revision = "0004_city_events"
down_revision = "0003_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""
        CREATE TABLE city_events (
            id            BIGSERIAL   PRIMARY KEY,
            type          TEXT        NOT NULL CHECK (type IN ('ISSUE','ALARM','VENUE','PROMOTION')),
            status        TEXT        NOT NULL DEFAULT 'ACTIVE' CHECK (status IN (
                              'ACTIVE','SCHEDULED','RESOLVED','EXPIRED')),
            title         TEXT        NOT NULL,
            description   TEXT        NOT NULL,
            category      TEXT        CHECK (category IN (
                              'WATER','ROADS','WASTE','GREENERY','LIGHTING','PUBLIC_TRANSPORT','OTHER')),
            severity      TEXT        CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
            location_text TEXT,
            address       TEXT,
            lat           DOUBLE PRECISION,
            lng           DOUBLE PRECISION,
            source        TEXT        NOT NULL DEFAULT 'CITY' CHECK (source IN ('CITY','USER','BUSINESS')),
            reporter_id   BIGINT      NOT NULL REFERENCES users (id),
            starts_at     TIMESTAMPTZ,
            ends_at       TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX city_events_status_idx ON city_events (status);")
    execute("CREATE INDEX city_events_type_idx ON city_events (type);")
    execute("CREATE INDEX city_events_reporter_id_idx ON city_events (reporter_id);")


def downgrade() -> None:
    execute("DROP TABLE IF EXISTS city_events;")
