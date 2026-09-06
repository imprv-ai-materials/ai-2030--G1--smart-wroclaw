"""Set a user's role (ADMIN / BASIC).

    python api/tests/manual/set_user_role.py <email> <ADMIN|BASIC>

ADMIN accounts additionally see the per-turn agent trace under each chat reply.
Prefer the pypyr shortcut: `pypyr set_role user=<email> role=ADMIN`. Needs Postgres
up + migrations applied (reads CONFIG__POSTGRES__* from api/.env, like the app).
"""

import sys

from api.bootstrap import get_bootstrap
from api.contexts_boundaries.auth_bc.models import UserRole


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: set_user_role.py <email> <ADMIN|BASIC>")
    email = sys.argv[1].strip().lower()
    try:
        role = UserRole(sys.argv[2].strip().upper())
    except ValueError:
        raise SystemExit(f"invalid role {sys.argv[2]!r} — use ADMIN or BASIC")

    repo = get_bootstrap().users_repository
    user = repo.get_by_email(email)
    if user is None:
        raise SystemExit(f"no user with email {email!r}")
    updated = repo.set_role(user.id, role)
    print(f"✓ {updated.email} → role={updated.role.value}")


if __name__ == "__main__":
    main()
