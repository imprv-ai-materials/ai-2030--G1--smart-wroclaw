"""Application configuration.

Mirrors the imprv services: a single pydantic-settings `Config` tree loaded from
`CONFIG__`-prefixed env vars (nested with `__`). Example:

    CONFIG__POSTGRES__HOST=db
    CONFIG__OPENAI__API_KEY=sk-...
    CONFIG__SPECIALIST__API_KEY=super-secret

Every sub-config with sensible defaults is optional so the stack boots in local
dev with only Postgres configured.
"""

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAIConfig(BaseModel):
    api_key: str | None = None
    default_model_name: str = "gpt-5.4"


class PostgresConfig(BaseModel):
    host: str
    port: int = 5432
    db: str
    user: str
    password: str
    pool_min_connection_count: int = 1
    pool_max_connection_count: int = 10
    pool_max_lifetime_s: float = 300.0

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class AssistantConfig(BaseModel):
    """City-maintenance Q&A assistant.

    `dev_citizen_id` is the fixed citizen the API attributes requests to when no
    `X-Citizen-Id` header is present (auth is a placeholder in this first draft).
    """

    dev_citizen_id: int = 1
    model: str = "gpt-5.4"
    title_max_chars: int = 60


class ReportsConfig(BaseModel):
    """Citizen issue reports + the specialist HITL review loop.

    `auto_publish_threshold` is reserved: a future iteration may let a triage
    with confidence above it skip the queue. For now EVERY report waits for a
    human specialist — the loop is always on.
    """

    triage_model: str = "gpt-5.4"
    auto_publish_threshold: float = 1.1  # > 1.0 → effectively never auto-publish
    default_department: str = "Centrum Zarządzania Kryzysowego"


class SpecialistConfig(BaseModel):
    """Auth for the specialist HITL console.

    A single shared API key checked against the `X-Specialist-Key` header. Good
    enough for the first draft; swap for real per-user auth (Auth0 / SSO) later.
    """

    api_key: str = "dev-specialist"
    dev_specialist_id: str = "specialist-1"


class AppConfig(BaseModel):
    """App-level auth + public-URL settings.

    `jwt_secret` / `password_pepper` MUST be overridden in any real deployment
    (see `.env`). `ui_base_url` is the public origin of the citizen Next.js app
    — email confirmation / password-reset links point back into it.
    """

    name: str = "Smart Wrocław"
    jwt_secret: str = "dev-insecure-change-me"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days
    password_pepper: str = ""
    ui_base_url: str = "http://localhost:3100"
    # Confirmation / reset token lifetimes.
    email_token_ttl_hours: int = 48
    reset_token_ttl_hours: int = 2


class ResendConfig(BaseModel):
    """Transactional email via Resend (https://resend.com).

    With no `api_key` the stack falls back to a console email client that just
    logs the message (and the confirmation/reset link) — so the whole email
    flow works end-to-end in local dev without a Resend account.
    """

    api_key: str | None = None
    from_email: str = "Smart Wrocław <onboarding@resend.dev>"


class HereConfig(BaseModel):
    """HERE Geocoding & Search — address string → coordinates.

    With no `api_key` the geocoding enrichment is skipped (events keep whatever
    coordinates they were created with). `bbox` (west,south,east,north) hard-
    restricts matches to Wrocław so a street name can't resolve to a neighbouring
    town. Env: `CONFIG__HERE__API_KEY`.
    """

    api_key: str | None = None
    bbox: str = "16.82,51.02,17.16,51.20"
    lang: str = "pl"


class Config(BaseSettings):
    postgres: PostgresConfig
    openai: OpenAIConfig = OpenAIConfig()
    assistant: AssistantConfig = AssistantConfig()
    reports: ReportsConfig = ReportsConfig()
    specialist: SpecialistConfig = SpecialistConfig()
    app: AppConfig = AppConfig()
    resend: ResendConfig = ResendConfig()
    here: HereConfig = HereConfig()

    enable_query_logging: bool = False

    model_config = SettingsConfigDict(
        env_prefix="CONFIG__",
        env_nested_delimiter="__",
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="allow",
        enable_decoding=False,
    )


config = Config()
