"""add role to users (ADMIN / BASIC)

Revision ID: 0007_user_role
Revises: 0006_chat
Create Date: 2026-09-06 12:00:00.000000

A coarse authorization level per account. BASIC (the default for every resident)
is a normal user; ADMIN additionally sees the per-turn agent trace under each chat
reply. Promote with `pypyr set_role user=<email> role=ADMIN`.
"""

from api.adapters.db.migrations.versions import execute

revision = "0007_user_role"
down_revision = "0006_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'BASIC'
            CHECK (role IN ('BASIC', 'ADMIN'));
        """
    )


def downgrade() -> None:
    execute("ALTER TABLE users DROP COLUMN IF EXISTS role;")
