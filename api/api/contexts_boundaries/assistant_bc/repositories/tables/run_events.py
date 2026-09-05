from pypika.queries import Table

run_events_table = Table("run_events")
# CREATE TABLE run_events (
#     id               BIGSERIAL PRIMARY KEY,
#     run_id           BIGINT      NOT NULL REFERENCES assistant_runs (id) ON DELETE CASCADE,
#     conversation_id  BIGINT      NOT NULL,
#     type             TEXT        NOT NULL,
#     data             JSONB       NOT NULL DEFAULT '{}',
#     created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX run_events_run_id_idx ON run_events (run_id);
