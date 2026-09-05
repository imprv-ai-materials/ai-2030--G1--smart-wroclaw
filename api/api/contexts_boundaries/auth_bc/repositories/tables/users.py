from pypika.queries import Table

users_table = Table("users")
# CREATE TABLE users (
#     id              BIGSERIAL   PRIMARY KEY,
#     email           TEXT        NOT NULL UNIQUE,
#     password_hash   TEXT        NOT NULL,
#     email_confirmed BOOLEAN     NOT NULL DEFAULT FALSE,
#     phone           TEXT,                            -- reserved (business reporters)
#     created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
#     updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE UNIQUE INDEX users_email_key ON users (lower(email));
