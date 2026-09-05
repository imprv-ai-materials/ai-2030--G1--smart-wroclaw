"""Auth for the REST layer — real resident login only.

`Authorization: Bearer <jwt>` is verified against `config.app.jwt_secret` and the
account is re-fetched from the DB each request, so a deleted account can't keep
using a live token.

    authenticate               → a logged-in resident (401 if missing/invalid)
    require_confirmed_user  → same, but the email must be confirmed
    optional_user           → the resident if a valid bearer is present, else
                                 None (lets the chat run anonymously)
"""

import jwt
from api.bootstrap import Bootstrap, get_bootstrap_dep
from api.contexts_boundaries.auth_bc.models import User
from api.contexts_boundaries.auth_bc.security import decode_access_token
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=True)


def authenticate(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> User:
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

    user = bootstrap.users_repository.get_by_id(int(decoded["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="konto już nie istnieje",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_confirmed_user(user: User = Depends(authenticate)) -> User:
    """Authorize an action that needs a *confirmed* email (e.g. filing an event).

    Per the spec: "aby zgłosić zdarzenie należy się zalogować i potwierdzić
    adres email"."""
    if not user.email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="potwierdź adres email, aby zgłaszać zdarzenia",
        )
    return user


_optional_bearer = HTTPBearer(auto_error=False)


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> User | None:
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
    return bootstrap.users_repository.get_by_id(int(decoded["sub"]))
