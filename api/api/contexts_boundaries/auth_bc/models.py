from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TokenKind(StrEnum):
    """What a single-use `auth_tokens` row authorizes."""

    CONFIRM_EMAIL = "CONFIRM_EMAIL"
    RESET_PASSWORD = "RESET_PASSWORD"


class User(BaseModel):
    """A resident account.

    Login identity is the email address. `email_confirmed` gates the ability to
    file events (a user must confirm their address first — see the report
    flow). `phone` is reserved for business reporters and is currently never
    collected ("skip passing the telephone number for now").
    """

    id: int
    email: str
    password_hash: str
    email_confirmed: bool = False
    phone: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        return cls(
            id=data["id"],
            email=data["email"],
            password_hash=data["password_hash"],
            email_confirmed=bool(data.get("email_confirmed")),
            phone=data.get("phone"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


class AuthToken(BaseModel):
    """A single-use, hashed token backing email confirmation / password reset.

    Only the SHA-256 `token_hash` is stored; the raw token travels in the email
    link and is never persisted. A token is spent once `used_at` is set."""

    id: int
    user_id: int
    kind: TokenKind
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthToken":
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            kind=TokenKind(data["kind"]),
            token_hash=data["token_hash"],
            expires_at=data["expires_at"],
            used_at=data.get("used_at"),
            created_at=data["created_at"],
        )
