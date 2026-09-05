from pypika.queries import Table

citizens_table = Table("citizens")
# CREATE TABLE citizens (
#     id              BIGSERIAL   PRIMARY KEY,
#     email           TEXT        NOT NULL UNIQUE,
#     password_hash   TEXT        NOT NULL,
#     email_confirmed BOOLEAN     NOT NULL DEFAULT FALSE,
#     phone           TEXT,                            -- reserved (business reporters)
#     created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
#     updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
# );
# CREATE UNIQUE INDEX citizens_email_key ON citizens (lower(email));
