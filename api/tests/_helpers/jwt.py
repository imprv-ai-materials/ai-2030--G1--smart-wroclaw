"""Auth helpers for API tests.

`POST /events` (and the rest of the real-login surface) authenticates a resident
from an `Authorization: Bearer <jwt>` header, then re-fetches them from the DB.
So a test must (1) persist the citizen and (2) sign a matching token — this
helper does the signing, using the app's own `issue_access_token` so the payload
shape can never drift from production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from api.contexts_boundaries.auth_bc.security import issue_access_token

if TYPE_CHECKING:
    from api.config import Config


def auth_headers(citizen_id: int, email: str, config: "Config") -> dict[str, str]:
    """Return an `Authorization` header for a citizen (`X-Citizen-Id` free)."""
    token, _ = issue_access_token(citizen_id, email, config)
    return {"Authorization": f"Bearer {token}"}
