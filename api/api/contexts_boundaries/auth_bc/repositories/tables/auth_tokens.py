from pypika.queries import Table

auth_tokens_table = Table("auth_tokens")
# CREATE TABLE auth_tokens (
#     id          BIGSERIAL   PRIMARY KEY,
#     user_id  BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
#     kind        TEXT        NOT NULL CHECK (kind IN ('CONFIRM_EMAIL','RESET_PASSWORD')),
#     token_hash  TEXT        NOT NULL UNIQUE,     -- SHA-256 of the raw token
#     expires_at  TIMESTAMPTZ NOT NULL,
#     used_at     TIMESTAMPTZ,
#     created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE INDEX auth_tokens_user_id_idx ON auth_tokens (user_id);
