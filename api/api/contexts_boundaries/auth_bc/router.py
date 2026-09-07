"""REST router for user authentication.

    POST /auth/register                 create an account (sends a confirm email)
    POST /auth/login                     email + password → JWT
    GET  /auth/me                        the logged-in resident (Bearer)
    POST /auth/confirm-email             spend a confirmation token
    POST /auth/resend-confirmation       re-send the confirm email (neutral)
    POST /auth/request-password-reset    send a reset link (neutral)
    POST /auth/reset-password            spend a reset token → new password
    POST /auth/change-password           change password while logged in (Bearer)
"""

from api.bootstrap import get_auth_service_dep
from api.contexts_boundaries.auth_bc.dependencies import authenticate
from api.contexts_boundaries.auth_bc.models import User
from api.contexts_boundaries.auth_bc.schemas import (
    ChangePasswordRequest,
    ConfirmEmailRequest,
    ConfirmEmailResponse,
    EmailRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from api.contexts_boundaries.auth_bc.services import AbstractAuthService
from fastapi import APIRouter, Depends, status

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def register(
    body: RegisterRequest,
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> MessageResponse:
    auth_service.register(body.email, body.password)
    return MessageResponse(
        message="Konto utworzone. Sprawdź skrzynkę email i potwierdź adres."
    )


@auth_router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> TokenResponse:
    return auth_service.login(body.email, body.password)


@auth_router.get("/me", response_model=MeResponse)
def me(
    current: User = Depends(authenticate),
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> MeResponse:
    return auth_service.get_me(current.id)


@auth_router.post("/confirm-email", response_model=ConfirmEmailResponse)
def confirm_email(
    body: ConfirmEmailRequest,
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> ConfirmEmailResponse:
    auth_service.confirm_email(body.token)
    return ConfirmEmailResponse(message="Adres email został potwierdzony.")


@auth_router.post(
    "/resend-confirmation", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def resend_confirmation(
    body: EmailRequest,
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> MessageResponse:
    auth_service.resend_confirmation(body.email)
    return MessageResponse(
        message="Jeśli konto istnieje i nie jest potwierdzone, wysłaliśmy nowy link."
    )


@auth_router.post(
    "/request-password-reset", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def request_password_reset(
    body: EmailRequest,
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> MessageResponse:
    auth_service.request_password_reset(body.email)
    return MessageResponse(message="Jeśli konto istnieje, wysłaliśmy link do resetu hasła.")


@auth_router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    body: ResetPasswordRequest,
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> MessageResponse:
    auth_service.reset_password(body.token, body.new_password)
    return MessageResponse(message="Hasło zostało zmienione. Możesz się zalogować.")


@auth_router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    current: User = Depends(authenticate),
    auth_service: AbstractAuthService = Depends(get_auth_service_dep),
) -> MessageResponse:
    auth_service.change_password(current.id, body.current_password, body.new_password)
    return MessageResponse(message="Hasło zostało zmienione.")
