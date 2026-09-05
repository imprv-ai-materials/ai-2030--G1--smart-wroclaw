"""create user accounts + single-use auth token tables

Revision ID: 0003_auth
Revises:
Create Date: 2026-09-04 10:00:00.000000

Base migration. Real resident login: `users` holds email + bcrypt password hash
and an `email_confirmed` flag (a user must confirm before filing events).
`auth_tokens` backs email confirmation and password reset — only the SHA-256 hash
of each single-use token is stored; the raw token lives only in the link.

A fixed system "City" account (id 1) is seeded so municipal / seed / ingest
`city_events` can satisfy the NOT NULL `reporter_id` FK (see 0004 + the
`SYSTEM_USER_ID` constant in the events service). It has no usable password, so
it can never be logged into.
"""

from api.adapters.db.migrations.versions import execute

revision = "0003_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""
        CREATE TABLE users (
            id              BIGSERIAL   PRIMARY KEY,
            email           TEXT        NOT NULL,
            password_hash   TEXT        NOT NULL,
            email_confirmed BOOLEAN     NOT NULL DEFAULT FALSE,
            phone           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE UNIQUE INDEX users_email_key ON users (lower(email));")

    # System "City" account — owns municipal / seed events. `password_hash` is a
    # non-bcrypt sentinel so login (bcrypt verify) can never succeed for it.
    execute("""
        INSERT INTO users (id, email, password_hash, email_confirmed)
        VALUES (1, 'city@smart-wroclaw.pl', 'SYSTEM-ACCOUNT-NO-LOGIN', TRUE);
        """)
    # Advance the BIGSERIAL sequence past the explicit id=1 so the next real
    # signup doesn't collide on id 1.
    execute("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT MAX(id) FROM users));")

    execute("""
        CREATE TABLE auth_tokens (
            id          BIGSERIAL   PRIMARY KEY,
            user_id     BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            kind        TEXT        NOT NULL CHECK (kind IN ('CONFIRM_EMAIL','RESET_PASSWORD')),
            token_hash  TEXT        NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX auth_tokens_user_id_idx ON auth_tokens (user_id);")


def downgrade() -> None:
    execute("DROP TABLE IF EXISTS auth_tokens;")
    execute("DROP TABLE IF EXISTS users;")
