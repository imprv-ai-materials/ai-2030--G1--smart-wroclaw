import sqlalchemy as sa
from alembic import op


def execute(statement: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.sql.text(statement))
