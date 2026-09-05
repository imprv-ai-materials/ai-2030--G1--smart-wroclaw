from pypika.queries import Table

report_reviews_table = Table("report_reviews")
# CREATE TABLE report_reviews (
#     id               BIGSERIAL PRIMARY KEY,
#     report_id        BIGINT      NOT NULL REFERENCES issue_reports (id) ON DELETE CASCADE,
#     specialist_id    TEXT        NOT NULL,
#     decision         TEXT        NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
#     edited_category  TEXT,
#     edited_severity  TEXT,
#     edited_department TEXT,
#     public_response  TEXT,
#     comment          TEXT        NOT NULL DEFAULT '',
#     created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX report_reviews_report_id_idx ON report_reviews (report_id);
