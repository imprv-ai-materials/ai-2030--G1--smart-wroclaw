"""Request/response schemas for the auth BC.

Email is validated with a light regex rather than pydantic's `EmailStr` to avoid
pulling in the `email-validator` dependency for this first draft.
"""

import re

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _EmailModel(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("nieprawidłowy adres email")
        return v


class RegisterRequest(_EmailModel):
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(_EmailModel):
    password: str


class EmailRequest(_EmailModel):
    """Used by resend-confirmation and request-password-reset."""


class ConfirmEmailRequest(BaseModel):
    token: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    email_confirmed: bool = False


class MeResponse(BaseModel):
    id: int
    email: str
    email_confirmed: bool
    phone: str | None = None


class ConfirmEmailResponse(BaseModel):
    message: str
    email_confirmed: bool = True


class MessageResponse(BaseModel):
    message: str
