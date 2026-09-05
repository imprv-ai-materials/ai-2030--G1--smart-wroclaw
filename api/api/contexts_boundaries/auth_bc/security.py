"""Low-level auth primitives: password hashing, JWT issuing/decoding, and the
single-use token helpers used by email confirmation / password reset.

Kept free of FastAPI and of the repositories so both `AuthService` and the
request dependency (`dependencies.authenticate`) can share it without a cycle.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from api.config import Config

JWT_ALGORITHM = "HS256"


# ── passwords ───────────────────────────────────────────────────────────────
def hash_password(plain: str, pepper: str) -> str:
    return bcrypt.hashpw((plain + pepper).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str, pepper: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw((plain + pepper).encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ── JWT ─────────────────────────────────────────────────────────────────────
def issue_access_token(user_id: int, email: str, config: Config) -> tuple[str, int]:
    """Sign and return (token, expires_in_seconds)."""
    expires = timedelta(minutes=config.app.jwt_expires_minutes)
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + expires,
    }
    token = jwt.encode(payload, config.app.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, int(expires.total_seconds())


def decode_access_token(token: str, config: Config) -> dict:
    """Raises `jwt.PyJWTError` subclasses on invalid/expired tokens."""
    return jwt.decode(token, config.app.jwt_secret, algorithms=[JWT_ALGORITHM])


# ── single-use email/reset tokens ───────────────────────────────────────────
def generate_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). The raw token goes in the email link; only
    the hash is ever stored."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
