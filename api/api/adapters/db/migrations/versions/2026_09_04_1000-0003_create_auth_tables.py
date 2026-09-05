"""create citizen accounts + single-use auth token tables

Revision ID: 0003_auth
Revises: 0002_reports
Create Date: 2026-09-04 10:00:00.000000

Real resident login: `citizens` holds email + bcrypt password hash and an
`email_confirmed` flag (a citizen must confirm before filing events).
`auth_tokens` backs email confirmation and password reset — only the SHA-256
hash of each single-use token is stored; the raw token lives only in the link.
"""

from api.adapters.db.migrations.versions import execute

revision = "0003_auth"
down_revision = "0002_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""
        CREATE TABLE citizens (
            id              BIGSERIAL   PRIMARY KEY,
            email           TEXT        NOT NULL,
            password_hash   TEXT        NOT NULL,
            email_confirmed BOOLEAN     NOT NULL DEFAULT FALSE,
            phone           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE UNIQUE INDEX citizens_email_key ON citizens (lower(email));")

    execute("""
        CREATE TABLE auth_tokens (
            id          BIGSERIAL   PRIMARY KEY,
            citizen_id  BIGINT      NOT NULL REFERENCES citizens (id) ON DELETE CASCADE,
            kind        TEXT        NOT NULL CHECK (kind IN ('CONFIRM_EMAIL','RESET_PASSWORD')),
            token_hash  TEXT        NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            used_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """)
    execute("CREATE INDEX auth_tokens_citizen_id_idx ON auth_tokens (citizen_id);")


def downgrade() -> None:
    execute("DROP TABLE IF EXISTS auth_tokens;")
    execute("DROP TABLE IF EXISTS citizens;")
