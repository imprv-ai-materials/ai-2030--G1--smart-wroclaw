"""Test-database bootstrap.

The app has no ORM metadata to `create_all()` — schema lives only in the raw-SQL
Alembic migrations. So an integration run needs a real Postgres with the schema
built by `alembic upgrade head`. This helper:

1. creates the throwaway test database if it doesn't exist (connecting to the
   server's `postgres` maintenance DB), then
2. migrates it to head.

`conftest._db_schema` calls it once per session and turns any failure into a
`pytest.skip`, so the integration layer is a no-op when no local stack is up.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.config import Config

# api/tests/_helpers/db.py -> parents[2] == api/ (where alembic.ini lives).
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def ensure_test_database(config: "Config") -> None:
    """Create (if missing) and migrate the configured test database to head."""
    _create_database_if_missing(config)
    _upgrade_to_head()


def _create_database_if_missing(config: "Config") -> None:
    import psycopg

    pg = config.postgres
    admin_conninfo = f"host={pg.host} port={pg.port} dbname=postgres user={pg.user} password={pg.password}"
    # autocommit: CREATE DATABASE cannot run inside a transaction block.
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (pg.db,)).fetchone()
        if not exists:
            # Identifier can't be parametrised; pg.db comes from our own config.
            conn.execute(f'CREATE DATABASE "{pg.db}"')


def _upgrade_to_head() -> None:
    from alembic import command
    from alembic.config import Config as AlembicConfig

    # env.py reads the URL from `api.config` (already pinned at the test DB),
    # so we only have to point Alembic at its ini + script location.
    alembic_cfg = AlembicConfig(str(ALEMBIC_INI))
    command.upgrade(alembic_cfg, "head")
