from pypika.queries import Table

conversations_table = Table("conversations")
# CREATE TABLE conversations (
#     id          BIGSERIAL PRIMARY KEY,
#     citizen_id  BIGINT      NOT NULL,
#     title       TEXT,
#     created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
#     updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX conversations_citizen_id_idx ON conversations (citizen_id);
