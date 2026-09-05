from pypika.queries import Table

messages_table = Table("messages")
# CREATE TABLE messages (
#     id               BIGSERIAL PRIMARY KEY,
#     conversation_id  BIGINT      NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
#     run_id           BIGINT,
#     role             TEXT        NOT NULL CHECK (role IN ('USER', 'ASSISTANT', 'SYSTEM')),
#     content          TEXT        NOT NULL DEFAULT '',
#     created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX messages_conversation_id_idx ON messages (conversation_id);
