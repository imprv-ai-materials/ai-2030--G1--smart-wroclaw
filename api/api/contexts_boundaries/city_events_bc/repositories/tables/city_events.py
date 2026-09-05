from pypika.queries import Table

city_events_table = Table("city_events")
# CREATE TABLE city_events (
#     id            BIGSERIAL   PRIMARY KEY,
#     type          TEXT        NOT NULL CHECK (type IN (
#                       'ISSUE','ALARM','VENUE','PROMOTION',
#                       'MISSING_PET','HAZARD','OUTAGE','ROADWORKS','COMMUNITY')),
#     status        TEXT        NOT NULL DEFAULT 'ACTIVE' CHECK (status IN (
#                       'ACTIVE','SCHEDULED','RESOLVED','EXPIRED')),
#     title         TEXT        NOT NULL,
#     description   TEXT        NOT NULL,
#     category      TEXT        CHECK (category IN (
#                       'WATER','ROADS','WASTE','GREENERY','LIGHTING','PUBLIC_TRANSPORT','OTHER')),
#     severity      TEXT        CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
#     location_text TEXT,
#     address       TEXT,
#     lat           DOUBLE PRECISION,
#     lng           DOUBLE PRECISION,
#     source        TEXT        NOT NULL DEFAULT 'CITY' CHECK (source IN ('CITY','USER','BUSINESS')),
#     reporter_id   BIGINT,             -- users.id when source = USER/BUSINESS
#     starts_at     TIMESTAMPTZ,
#     ends_at       TIMESTAMPTZ,
#     -- structured / reportable columns (migration 0005):
#     subtype       TEXT,               -- refine within a type (POTHOLE, CONCERT, …)
#     district      TEXT,               -- Wrocław osiedle — key reporting dimension
#     resolved_at   TIMESTAMPTZ,        -- feeds time-to-resolution metrics
#     expires_at    TIMESTAMPTZ,        -- auto-expiry (≠ ends_at)
#     confirmations INTEGER     NOT NULL DEFAULT 0,     -- "ja też to widzę"
#     verified      BOOLEAN     NOT NULL DEFAULT FALSE, -- moderator-verified
#     contact_phone TEXT,               -- e.g. owner of a missing pet
#     image_url     TEXT,               -- primary photo
#     details       JSONB       NOT NULL DEFAULT '{}',  -- per-type long tail
#     created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
#     updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX city_events_status_idx   ON city_events (status);
# CREATE INDEX city_events_type_idx     ON city_events (type);
# CREATE INDEX city_events_district_idx ON city_events (district);
