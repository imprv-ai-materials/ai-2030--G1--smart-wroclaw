import abc
from datetime import datetime, timezone

from api.adapters.db import DBClient
from api.contexts_boundaries.auth_bc.models import User, UserRole
from api.contexts_boundaries.auth_bc.repositories.tables import users_table


class AbstractUsersRepository(abc.ABC):
    @abc.abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abc.abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abc.abstractmethod
    def create(self, email: str, password_hash: str, phone: str | None = None) -> User: ...

    @abc.abstractmethod
    def set_email_confirmed(self, user_id: int) -> User | None: ...

    @abc.abstractmethod
    def set_password_hash(self, user_id: int, password_hash: str) -> User | None: ...

    @abc.abstractmethod
    def set_role(self, user_id: int, role: UserRole) -> User | None: ...


class UsersRepository(AbstractUsersRepository):
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    def get_by_id(self, user_id: int) -> User | None:
        row = self._db.get_one(users_table, {"id": user_id})
        return User.from_dict(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        # The service normalises emails to lowercase before they ever reach the
        # repo, so an exact match is both correct and case-insensitive (and
        # avoids ILIKE treating `_`/`%` in a local part as wildcards).
        row = self._db.get_one(users_table, {"email": email.strip().lower()})
        return User.from_dict(row) if row else None

    def create(self, email: str, password_hash: str, phone: str | None = None) -> User:
        row = self._db.create_one(
            users_table,
            values={
                "email": email.strip().lower(),
                "password_hash": password_hash,
                "phone": phone,
                "email_confirmed": False,
            },
        )
        return User.from_dict(row)

    def set_email_confirmed(self, user_id: int) -> User | None:
        self._db.update_one(
            users_table,
            {"id": user_id},
            {"email_confirmed": True, "updated_at": datetime.now(tz=timezone.utc)},
        )
        return self.get_by_id(user_id)

    def set_password_hash(self, user_id: int, password_hash: str) -> User | None:
        self._db.update_one(
            users_table,
            {"id": user_id},
            {"password_hash": password_hash, "updated_at": datetime.now(tz=timezone.utc)},
        )
        return self.get_by_id(user_id)

    def set_role(self, user_id: int, role: UserRole) -> User | None:
        self._db.update_one(
            users_table,
            {"id": user_id},
            {"role": UserRole(role).value, "updated_at": datetime.now(tz=timezone.utc)},
        )
        return self.get_by_id(user_id)
