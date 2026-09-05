import abc
from datetime import datetime, timezone

from api.adapters.db import DBClient
from api.contexts_boundaries.auth_bc.models import Citizen
from api.contexts_boundaries.auth_bc.repositories.tables import citizens_table


class AbstractCitizensRepository(abc.ABC):
    @abc.abstractmethod
    def get_by_id(self, citizen_id: int) -> Citizen | None: ...

    @abc.abstractmethod
    def get_by_email(self, email: str) -> Citizen | None: ...

    @abc.abstractmethod
    def create(self, email: str, password_hash: str, phone: str | None = None) -> Citizen: ...

    @abc.abstractmethod
    def set_email_confirmed(self, citizen_id: int) -> Citizen | None: ...

    @abc.abstractmethod
    def set_password_hash(self, citizen_id: int, password_hash: str) -> Citizen | None: ...


class CitizensRepository(AbstractCitizensRepository):
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    def get_by_id(self, citizen_id: int) -> Citizen | None:
        row = self._db.get_one(citizens_table, {"id": citizen_id})
        return Citizen.from_dict(row) if row else None

    def get_by_email(self, email: str) -> Citizen | None:
        # The service normalises emails to lowercase before they ever reach the
        # repo, so an exact match is both correct and case-insensitive (and
        # avoids ILIKE treating `_`/`%` in a local part as wildcards).
        row = self._db.get_one(citizens_table, {"email": email.strip().lower()})
        return Citizen.from_dict(row) if row else None

    def create(self, email: str, password_hash: str, phone: str | None = None) -> Citizen:
        row = self._db.create_one(
            citizens_table,
            values={
                "email": email.strip().lower(),
                "password_hash": password_hash,
                "phone": phone,
                "email_confirmed": False,
            },
        )
        return Citizen.from_dict(row)

    def set_email_confirmed(self, citizen_id: int) -> Citizen | None:
        self._db.update_one(
            citizens_table,
            {"id": citizen_id},
            {"email_confirmed": True, "updated_at": datetime.now(tz=timezone.utc)},
        )
        return self.get_by_id(citizen_id)

    def set_password_hash(self, citizen_id: int, password_hash: str) -> Citizen | None:
        self._db.update_one(
            citizens_table,
            {"id": citizen_id},
            {"password_hash": password_hash, "updated_at": datetime.now(tz=timezone.utc)},
        )
        return self.get_by_id(citizen_id)
