from pypika.queries import Table

issue_reports_table = Table("issue_reports")
# CREATE TABLE issue_reports (
#     id              BIGSERIAL PRIMARY KEY,
#     citizen_id      BIGINT      NOT NULL,
#     title           TEXT        NOT NULL,
#     description     TEXT        NOT NULL,
#     category        TEXT        CHECK (category IN (
#                         'WATER','ROADS','WASTE','GREENERY','LIGHTING','PUBLIC_TRANSPORT','OTHER')),
#     location_text   TEXT,
#     lat             DOUBLE PRECISION,
#     lng             DOUBLE PRECISION,
#     status          TEXT        NOT NULL DEFAULT 'SUBMITTED' CHECK (status IN (
#                         'SUBMITTED','TRIAGING','PENDING_REVIEW','APPROVED','REJECTED','PUBLISHED','FAILED')),
#     severity        TEXT        CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
#     department      TEXT,
#     triage          JSONB,               -- the AI TriageResult proposal
#     public_response TEXT,                -- set on approval; citizen-visible
#     reviewed_by     TEXT,
#     reviewed_at     TIMESTAMPTZ,
#     created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
#     updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX issue_reports_citizen_id_idx ON issue_reports (citizen_id);
# CREATE INDEX issue_reports_status_idx     ON issue_reports (status);
