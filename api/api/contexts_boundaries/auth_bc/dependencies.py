"""Auth for the REST layer.

Two identity models coexist during this migration:

* **JWT citizen** (`authenticate` / `require_confirmed_citizen`) — the real
  resident login: `Authorization: Bearer <jwt>`, verified against
  `config.app.jwt_secret`, re-fetched from the DB each request so a deleted
  account can't keep using a live token. Used by the auth + events write APIs.

* **Header placeholders** (`citizen` / `specialist`) — the original first-draft
  identities kept for back-compat with the assistant Q&A and the specialist HITL
  console, which haven't been migrated to real login yet:
    - Citizen — `X-Citizen-Id`, falling back to `config.assistant.dev_citizen_id`.
    - Specialist — shared secret in `X-Specialist-Key`.
"""

from dataclasses import dataclass

import jwt
from api.bootstrap import Bootstrap, get_bootstrap_dep
from api.contexts_boundaries.auth_bc.models import Citizen
from api.contexts_boundaries.auth_bc.security import decode_access_token
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass
class CitizenContext:
    citizen_id: int


@dataclass
class SpecialistContext:
    specialist_id: str


#
# JWT CITIZEN (real login)
#
_bearer = HTTPBearer(auto_error=True)


def authenticate(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> Citizen:
    """Resolve the logged-in resident from a bearer JWT."""
    config = bootstrap.config
    try:
        decoded = decode_access_token(credentials.credentials, config)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sesja wygasła — zaloguj się ponownie",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="nieprawidłowy token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    citizen = bootstrap.citizens_repository.get_by_id(int(decoded["sub"]))
    if citizen is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="konto już nie istnieje",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return citizen


def require_confirmed_citizen(citizen: Citizen = Depends(authenticate)) -> Citizen:
    """Authorize an action that needs a *confirmed* email (e.g. filing an event).

    Per the spec: "aby zgłosić zdarzenie należy się zalogować i potwierdzić
    adres email"."""
    if not citizen.email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="potwierdź adres email, aby zgłaszać zdarzenia",
        )
    return citizen


_optional_bearer = HTTPBearer(auto_error=False)


def optional_citizen(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> Citizen | None:
    """Resolve the logged-in resident if a valid bearer is present, else None.

    Lets the chat run anonymously and attach a conversation to an account only
    once the resident has logged in.
    """
    if credentials is None:
        return None
    try:
        decoded = decode_access_token(credentials.credentials, bootstrap.config)
    except jwt.PyJWTError:
        return None
    return bootstrap.citizens_repository.get_by_id(int(decoded["sub"]))


#
# HEADER PLACEHOLDERS (legacy assistant / specialist)
#
def citizen(
    x_citizen_id: int | None = Header(default=None, alias="X-Citizen-Id"),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> CitizenContext:
    citizen_id = x_citizen_id if x_citizen_id is not None else bootstrap.config.assistant.dev_citizen_id
    return CitizenContext(citizen_id=citizen_id)


def specialist(
    x_specialist_key: str | None = Header(default=None, alias="X-Specialist-Key"),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> SpecialistContext:
    expected = bootstrap.config.specialist.api_key
    if not x_specialist_key or x_specialist_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="brak uprawnień specjalisty (nagłówek X-Specialist-Key)",
        )
    return SpecialistContext(specialist_id=bootstrap.config.specialist.dev_specialist_id)
