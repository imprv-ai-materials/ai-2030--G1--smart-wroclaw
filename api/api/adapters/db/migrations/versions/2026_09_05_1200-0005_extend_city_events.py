"""extend city_events: new types + structured (reportable) columns

Revision ID: 0005_city_events_extra
Revises: 0004_city_events
Create Date: 2026-09-05 12:00:00.000000

Second layer of the event model. Widens the `type` CHECK to nine values
(adds MISSING_PET / HAZARD / OUTAGE / ROADWORKS / COMMUNITY) and adds a set of
structured, filterable columns so events stop being pure free text and become
*reportable*:

    subtype        refine within a type      (POTHOLE, CONCERT, TRAM_SUSPENDED…)
    district       Wrocław osiedle           (key reporting dimension)
    resolved_at    time-to-resolution metric
    expires_at     auto-expiry (≠ ends_at)
    confirmations  "ja też to widzę" corroboration count
    verified       moderator-verified flag
    contact_phone  e.g. owner of a missing pet
    image_url      primary photo
    details JSONB  per-type long tail (animal_species, utility, discount_pct…)

The long tail lives in `details` on purpose: adding a per-type field there needs
no migration. Fields worth reporting on get "promoted" to their own column later.
"""

from api.adapters.db.migrations.versions import execute

revision = "0005_city_events_extra"
down_revision = "0004_city_events"
branch_labels = None
depends_on = None

_NEW_TYPES = "'ISSUE','ALARM','VENUE','PROMOTION','MISSING_PET','HAZARD','OUTAGE','ROADWORKS','COMMUNITY'"
_OLD_TYPES = "'ISSUE','ALARM','VENUE','PROMOTION'"


def upgrade() -> None:
    # 1) Widen the type CHECK (inline single-column checks are named
    #    <table>_<column>_check by Postgres).
    execute("ALTER TABLE city_events DROP CONSTRAINT IF EXISTS city_events_type_check;")
    execute(f"ALTER TABLE city_events ADD CONSTRAINT city_events_type_check CHECK (type IN ({_NEW_TYPES}));")

    # 2) Structured columns. NOT-NULL ones carry defaults so existing rows and
    #    the factory/seed paths that omit them stay valid.
    execute("""
        ALTER TABLE city_events
            ADD COLUMN IF NOT EXISTS subtype       TEXT,
            ADD COLUMN IF NOT EXISTS district      TEXT,
            ADD COLUMN IF NOT EXISTS resolved_at   TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS expires_at    TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS confirmations INTEGER     NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS verified      BOOLEAN     NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS contact_phone TEXT,
            ADD COLUMN IF NOT EXISTS image_url     TEXT,
            ADD COLUMN IF NOT EXISTS details       JSONB       NOT NULL DEFAULT '{}';
        """)

    # 3) District is a primary reporting dimension → index it.
    execute("CREATE INDEX IF NOT EXISTS city_events_district_idx ON city_events (district);")


def downgrade() -> None:
    execute("DROP INDEX IF EXISTS city_events_district_idx;")
    execute("""
        ALTER TABLE city_events
            DROP COLUMN IF EXISTS subtype,
            DROP COLUMN IF EXISTS district,
            DROP COLUMN IF EXISTS resolved_at,
            DROP COLUMN IF EXISTS expires_at,
            DROP COLUMN IF EXISTS confirmations,
            DROP COLUMN IF EXISTS verified,
            DROP COLUMN IF EXISTS contact_phone,
            DROP COLUMN IF EXISTS image_url,
            DROP COLUMN IF EXISTS details;
        """)
    # Restore the original 4-value CHECK. Rows with new-type values must be gone
    # first, or this ADD CONSTRAINT will fail — expected for a real downgrade.
    execute("ALTER TABLE city_events DROP CONSTRAINT IF EXISTS city_events_type_check;")
    execute(f"ALTER TABLE city_events ADD CONSTRAINT city_events_type_check CHECK (type IN ({_OLD_TYPES}));")
