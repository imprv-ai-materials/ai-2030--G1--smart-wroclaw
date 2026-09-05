"""create citizen report + HITL review tables

Revision ID: 0002_reports
Revises: 0001_assistant
Create Date: 2026-08-31 13:00:00.000000

A citizen files an `issue_reports` row; the AI triage attaches a proposal
(`triage` JSONB) and moves it to PENDING_REVIEW. A specialist's decision is
recorded in `report_reviews` (audit trail) and flips the report to
PUBLISHED / REJECTED — the human-in-the-loop gate.
"""

from api.adapters.db.migrations.versions import execute

revision = "0002_reports"
down_revision = "0001_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""
        CREATE TABLE issue_reports (
            id              BIGSERIAL PRIMARY KEY,
            citizen_id      BIGINT      NOT NULL,
            title           TEXT        NOT NULL,
            description     TEXT        NOT NULL,
            category        TEXT        CHECK (category IN (
                                'WATER','ROADS','WASTE','GREENERY','LIGHTING','PUBLIC_TRANSPORT','OTHER')),
            location_text   TEXT,
            lat             DOUBLE PRECISION,
            lng             DOUBLE PRECISION,
            status          TEXT        NOT NULL DEFAULT 'SUBMITTED' CHECK (status IN (
                                'SUBMITTED','TRIAGING','PENDING_REVIEW','APPROVED','REJECTED','PUBLISHED','FAILED')),
            severity        TEXT        CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
            department      TEXT,
            triage          JSONB,
            public_response TEXT,
            reviewed_by     TEXT,
            reviewed_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX issue_reports_citizen_id_idx ON issue_reports (citizen_id);")
    execute("CREATE INDEX issue_reports_status_idx ON issue_reports (status);")

    execute("""
        CREATE TABLE report_reviews (
            id                BIGSERIAL PRIMARY KEY,
            report_id         BIGINT      NOT NULL REFERENCES issue_reports (id) ON DELETE CASCADE,
            specialist_id     TEXT        NOT NULL,
            decision          TEXT        NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
            edited_category   TEXT,
            edited_severity   TEXT,
            edited_department TEXT,
            public_response   TEXT,
            comment           TEXT        NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX report_reviews_report_id_idx ON report_reviews (report_id);")


def downgrade() -> None:
    execute("DROP TABLE IF EXISTS report_reviews;")
    execute("DROP TABLE IF EXISTS issue_reports;")
