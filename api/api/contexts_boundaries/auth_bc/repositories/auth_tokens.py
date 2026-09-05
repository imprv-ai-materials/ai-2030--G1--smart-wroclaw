import abc
from datetime import datetime, timezone

from api.adapters.db import DBClient
from api.contexts_boundaries.auth_bc.models import AuthToken, TokenKind
from api.contexts_boundaries.auth_bc.repositories.tables import auth_tokens_table


class AbstractAuthTokensRepository(abc.ABC):
    @abc.abstractmethod
    def create(
        self, user_id: int, kind: TokenKind, token_hash: str, expires_at: datetime
    ) -> AuthToken: ...

    @abc.abstractmethod
    def get_active(self, token_hash: str, kind: TokenKind) -> AuthToken | None:
        """Return an unused, unexpired token matching hash+kind, or None."""

    @abc.abstractmethod
    def mark_used(self, token_id: int) -> None: ...

    @abc.abstractmethod
    def invalidate_all(self, user_id: int, kind: TokenKind) -> None:
        """Spend any outstanding tokens of a kind — e.g. before issuing a fresh
        one so only the newest link works."""


class AuthTokensRepository(AbstractAuthTokensRepository):
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    def create(
        self, user_id: int, kind: TokenKind, token_hash: str, expires_at: datetime
    ) -> AuthToken:
        row = self._db.create_one(
            auth_tokens_table,
            values={
                "user_id": user_id,
                "kind": kind.value,
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )
        return AuthToken.from_dict(row)

    def get_active(self, token_hash: str, kind: TokenKind) -> AuthToken | None:
        row = self._db.get_one(
            auth_tokens_table,
            {
                "token_hash": token_hash,
                "kind": kind.value,
                "used_at__isnull": True,
                "expires_at__gt": datetime.now(tz=timezone.utc),
            },
        )
        return AuthToken.from_dict(row) if row else None

    def mark_used(self, token_id: int) -> None:
        self._db.update_one(
            auth_tokens_table,
            {"id": token_id},
            {"used_at": datetime.now(tz=timezone.utc)},
        )

    def invalidate_all(self, user_id: int, kind: TokenKind) -> None:
        self._db.update_one(
            auth_tokens_table,
            {"user_id": user_id, "kind": kind.value, "used_at__isnull": True},
            {"used_at": datetime.now(tz=timezone.utc)},
        )
