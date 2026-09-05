"""AuthService — registration, login, email confirmation, password reset.

The service owns the whole user-auth flow; the router is a thin HTTP shell
over it. Emails (confirmation / reset links) go out through the injected
`AbstractEmailClient`, which is the Resend client in prod and a console logger in
local dev.

Anti-enumeration: `resend_confirmation` and `request_password_reset` never
reveal whether an address exists — they always return the same neutral message.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import HTTPException, status

from api.adapters.email import AbstractEmailClient
from api.config import Config
from api.contexts_boundaries.auth_bc.models import User, TokenKind
from api.contexts_boundaries.auth_bc.repositories import (
    AbstractAuthTokensRepository,
    AbstractUsersRepository,
)
from api.contexts_boundaries.auth_bc.security import (
    generate_token,
    hash_password,
    hash_token,
    issue_access_token,
    verify_password,
)
from api.contexts_boundaries.auth_bc.schemas import MeResponse, TokenResponse
from loguru import logger


class AuthService:
    def __init__(
        self,
        users_repository: AbstractUsersRepository,
        auth_tokens_repository: AbstractAuthTokensRepository,
        email_client: AbstractEmailClient,
        config: Config,
    ) -> None:
        self._users = users_repository
        self._tokens = auth_tokens_repository
        self._email = email_client
        self._config = config

    # ── registration / login ─────────────────────────────────────────────────
    def register(self, email: str, password: str) -> User:
        email = email.strip().lower()
        if self._users.get_by_email(email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="konto z tym adresem email już istnieje",
            )
        user = self._users.create(
            email=email,
            password_hash=hash_password(password, self._config.app.password_pepper),
        )
        self._send_confirmation_email(user)
        return user

    def login(self, email: str, password: str) -> TokenResponse:
        user = self._users.get_by_email(email)
        if user is None or not verify_password(
            password, user.password_hash, self._config.app.password_pepper
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="nieprawidłowy email lub hasło",
            )
        token, expires_in = issue_access_token(user.id, user.email, self._config)
        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
            email_confirmed=user.email_confirmed,
        )

    def get_me(self, user_id: int) -> MeResponse:
        user = self._require_user(user_id)
        return MeResponse(
            id=user.id,
            email=user.email,
            email_confirmed=user.email_confirmed,
            phone=user.phone,
        )

    # ── email confirmation ───────────────────────────────────────────────────
    def confirm_email(self, raw_token: str) -> User:
        record = self._tokens.get_active(hash_token(raw_token), TokenKind.CONFIRM_EMAIL)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="link potwierdzający jest nieprawidłowy lub wygasł",
            )
        self._tokens.mark_used(record.id)
        user = self._users.set_email_confirmed(record.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="konto nie istnieje")
        return user

    def resend_confirmation(self, email: str) -> None:
        """Best-effort resend. Silent on unknown / already-confirmed addresses
        so this can't be used to probe for accounts."""
        user = self._users.get_by_email(email)
        if user is not None and not user.email_confirmed:
            self._send_confirmation_email(user)

    # ── password reset / change ──────────────────────────────────────────────
    def request_password_reset(self, email: str) -> None:
        user = self._users.get_by_email(email)
        if user is None:
            return  # anti-enumeration: pretend success
        raw, token_hash = generate_token()
        self._tokens.invalidate_all(user.id, TokenKind.RESET_PASSWORD)
        self._tokens.create(
            user_id=user.id,
            kind=TokenKind.RESET_PASSWORD,
            token_hash=token_hash,
            expires_at=self._expiry(self._config.app.reset_token_ttl_hours),
        )
        link = f"{self._ui_base}/auth/reset-password?token={raw}"
        self._email.send(
            to=user.email,
            subject=f"{self._config.app.name}: reset hasła",
            html=_reset_email_html(self._config.app.name, link),
            text=f"Aby zresetować hasło, otwórz: {link}\nLink jest ważny "
            f"{self._config.app.reset_token_ttl_hours} h.",
        )

    def reset_password(self, raw_token: str, new_password: str) -> None:
        record = self._tokens.get_active(hash_token(raw_token), TokenKind.RESET_PASSWORD)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="link resetu hasła jest nieprawidłowy lub wygasł",
            )
        self._tokens.mark_used(record.id)
        self._users.set_password_hash(
            record.user_id, hash_password(new_password, self._config.app.password_pepper)
        )

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        user = self._require_user(user_id)
        if not verify_password(
            current_password, user.password_hash, self._config.app.password_pepper
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="aktualne hasło jest nieprawidłowe",
            )
        self._users.set_password_hash(
            user.id, hash_password(new_password, self._config.app.password_pepper)
        )

    # ── internals ────────────────────────────────────────────────────────────
    def _send_confirmation_email(self, user: User) -> None:
        raw, token_hash = generate_token()
        self._tokens.invalidate_all(user.id, TokenKind.CONFIRM_EMAIL)
        self._tokens.create(
            user_id=user.id,
            kind=TokenKind.CONFIRM_EMAIL,
            token_hash=token_hash,
            expires_at=self._expiry(self._config.app.email_token_ttl_hours),
        )
        link = f"{self._ui_base}/auth/confirm?token={raw}"
        self._email.send(
            to=user.email,
            subject=f"{self._config.app.name}: potwierdź adres email",
            html=_confirm_email_html(self._config.app.name, link),
            text=f"Witaj w {self._config.app.name}! Potwierdź adres email: {link}\n"
            f"Link jest ważny {self._config.app.email_token_ttl_hours} h.",
        )
        logger.info("auth: confirmation email dispatched to user_id={}", user.id)

    def _require_user(self, user_id: int) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="konto nie istnieje")
        return user

    @property
    def _ui_base(self) -> str:
        return self._config.app.ui_base_url.rstrip("/")

    @staticmethod
    def _expiry(hours: int) -> datetime:
        return datetime.now(tz=timezone.utc) + timedelta(hours=hours)


def _confirm_email_html(app_name: str, link: str) -> str:
    safe = escape(link, quote=True)
    return (
        f"<div style='font-family:system-ui,sans-serif;color:#111'>"
        f"<h2 style='margin:0 0 12px'>{escape(app_name)}</h2>"
        f"<p>Dziękujemy za rejestrację. Potwierdź swój adres email, aby móc "
        f"zgłaszać zdarzenia w mieście.</p>"
        f"<p><a href='{safe}' style='display:inline-block;padding:10px 18px;"
        f"background:#111;color:#fff;text-decoration:none;border-radius:6px'>"
        f"Potwierdź adres email</a></p>"
        f"<p style='color:#666;font-size:13px'>Lub skopiuj link: {safe}</p></div>"
    )


def _reset_email_html(app_name: str, link: str) -> str:
    safe = escape(link, quote=True)
    return (
        f"<div style='font-family:system-ui,sans-serif;color:#111'>"
        f"<h2 style='margin:0 0 12px'>{escape(app_name)}</h2>"
        f"<p>Otrzymaliśmy prośbę o reset hasła. Jeśli to Ty, kliknij poniżej.</p>"
        f"<p><a href='{safe}' style='display:inline-block;padding:10px 18px;"
        f"background:#111;color:#fff;text-decoration:none;border-radius:6px'>"
        f"Ustaw nowe hasło</a></p>"
        f"<p style='color:#666;font-size:13px'>Jeśli to nie Ty, zignoruj tę wiadomość.</p></div>"
    )


__all__ = ["AuthService"]
