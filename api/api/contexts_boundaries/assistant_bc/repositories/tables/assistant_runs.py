from pypika.queries import Table

assistant_runs_table = Table("assistant_runs")
# CREATE TABLE assistant_runs (
#     id                    BIGSERIAL PRIMARY KEY,
#     conversation_id       BIGINT      NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
#     status                TEXT        NOT NULL DEFAULT 'queued'
#                           CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled')),
#     user_message_id       BIGINT      REFERENCES messages (id) ON DELETE SET NULL,
#     assistant_message_id  BIGINT      REFERENCES messages (id) ON DELETE SET NULL,
#     error                 TEXT,
#     cancel_requested      BOOLEAN     NOT NULL DEFAULT FALSE,
#     created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
#     started_at            TIMESTAMPTZ,
#     finished_at           TIMESTAMPTZ
# );
# CREATE INDEX assistant_runs_conversation_id_idx ON assistant_runs (conversation_id);
# -- at most one in-flight run per conversation
# CREATE UNIQUE INDEX assistant_runs_one_active_per_conversation
#     ON assistant_runs (conversation_id) WHERE status IN ('queued', 'running');
