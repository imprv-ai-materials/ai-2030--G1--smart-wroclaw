"""Composition root — the dependency-injection container.

Every adapter, repository, service and agent is wired here as a lazily-built
`cached_property`, so nothing connects to Postgres or OpenAI until first use.
`get_bootstrap()` returns a process-wide singleton that the FastAPI dependencies
(`get_bootstrap_dep`) and the Inngest worker functions both resolve against.

A small package, not a single file: `__init__` holds the container itself while
agent construction lives in `bootstrap.agents` (so "which prompt/model version"
has one home — see `api/ai/`). New bounded context → add its repo/service/agent
as properties here and mount its router in `main.py`.
"""

from functools import cached_property

from api.adapters.db import DBClient
from api.adapters.email import AbstractEmailClient, build_email_client
from api.adapters.geocoding import HereGeocodingClient
from api.adapters.llm import OpenAIClient
from api.adapters.notifications import NotificationBus
from api.adapters.websockets import WebSocketManager
from api.ai import load_current
from api.ai.analytics_agent import AbstractAnalyticsAgent
from api.ai.event_extractor import AbstractEventExtractor
from api.ai.geo_resolver import AbstractGeoResolver
from api.ai.guardrails_agent import AbstractGuardrailAgent
from api.ai.main_agent import AbstractMainAgent
from api.ai.report_agent import AbstractReportAgent
from api.ai.router_agent import AbstractRouterAgent
from api.ai.search_agent import AbstractSearchAgent
from api.bootstrap.agents import (
    get_analytics_agent,
    get_event_extractor,
    get_geo_resolver,
    get_guardrails_agent,
    get_report_agent,
    get_router_agent,
    get_search_agent,
)
from api.config import Config, config
from api.contexts_boundaries.auth_bc.repositories import (
    AbstractAuthTokensRepository,
    AbstractUsersRepository,
    AuthTokensRepository,
    UsersRepository,
)
from api.contexts_boundaries.auth_bc.services import AbstractAuthService, AuthService
from api.contexts_boundaries.chat_bc import (
    AbstractAgentRunsRepository,
    AbstractChatRepository,
    AgentRunsRepository,
    ChatRepository,
)
from api.contexts_boundaries.city_events_bc.repositories import (
    AbstractEventsRepository,
    EventsRepository,
)
from api.contexts_boundaries.city_events_bc.services import AbstractEventsService, EventsService
from psycopg_pool import ConnectionPool


class Bootstrap:
    def __init__(self, config: Config) -> None:
        self.config = config

    #
    # ADAPTERS
    #
    @cached_property
    def connection_pool(self) -> ConnectionPool:
        pg = self.config.postgres
        conninfo = f"host={pg.host} port={pg.port} dbname={pg.db} user={pg.user} password={pg.password}"
        pool = ConnectionPool(
            conninfo=conninfo,
            min_size=pg.pool_min_connection_count,
            max_size=pg.pool_max_connection_count,
            max_lifetime=pg.pool_max_lifetime_s,
            open=True,
        )
        return pool

    @cached_property
    def db_client(self) -> DBClient:
        return DBClient(
            connection_pool=self.connection_pool,
            enable_query_logging=self.config.enable_query_logging,
        )

    @cached_property
    def openai_client(self) -> OpenAIClient:
        return OpenAIClient(
            api_key=self.config.openai.api_key,
            default_model_name=self.config.openai.default_model_name,
        )

    @cached_property
    def here_client(self) -> HereGeocodingClient:
        return HereGeocodingClient(
            api_key=self.config.here.api_key,
            bbox=self.config.here.bbox,
            lang=self.config.here.lang,
        )

    @cached_property
    def websocket_manager(self) -> WebSocketManager:
        return WebSocketManager()

    @cached_property
    def notification_bus(self) -> NotificationBus:
        # The cross-process bridge: the worker NOTIFYs step progress, the API
        # LISTENs and relays it to the WebSocket sockets (see main.py).
        pg = self.config.postgres
        conninfo = f"host={pg.host} port={pg.port} dbname={pg.db} user={pg.user} password={pg.password}"
        return NotificationBus(conninfo)

    @cached_property
    def email_client(self) -> AbstractEmailClient:
        return build_email_client(self.config)

    #
    # AUTH BC
    #
    @cached_property
    def users_repository(self) -> AbstractUsersRepository:
        return UsersRepository(self.db_client)

    @cached_property
    def auth_tokens_repository(self) -> AbstractAuthTokensRepository:
        return AuthTokensRepository(self.db_client)

    @cached_property
    def auth_service(self) -> AbstractAuthService:
        return AuthService(
            users_repository=self.users_repository,
            auth_tokens_repository=self.auth_tokens_repository,
            email_client=self.email_client,
            config=self.config,
        )

    #
    # AI AGENTS — the sub-agents the main agent composes
    #
    @cached_property
    def guardrails_agent(self) -> AbstractGuardrailAgent:
        return get_guardrails_agent(self.openai_client, self.config)

    @cached_property
    def event_extractor(self) -> AbstractEventExtractor:
        return get_event_extractor(self.openai_client, self.config)

    @cached_property
    def router_agent(self) -> AbstractRouterAgent:
        return get_router_agent(self.openai_client, self.config)

    @cached_property
    def search_agent(self) -> AbstractSearchAgent:
        return get_search_agent(self.events_repository)

    @cached_property
    def report_agent(self) -> AbstractReportAgent:
        return get_report_agent(self.events_repository)

    @cached_property
    def analytics_agent(self) -> AbstractAnalyticsAgent:
        return get_analytics_agent(self.events_repository, self.openai_client, self.config)

    @cached_property
    def geo_resolver(self) -> AbstractGeoResolver:
        return get_geo_resolver(self.here_client)

    @cached_property
    def main_agent(self) -> AbstractMainAgent:
        # The one agent the app is — composes the sub-agents above into one turn.
        current = load_current("main_agent")
        return current.agent_class(
            guardrails=self.guardrails_agent,
            extractor=self.event_extractor,
            router=self.router_agent,
            search=self.search_agent,
            report=self.report_agent,
            analytics=self.analytics_agent,
            geo=self.geo_resolver,
            events_service=self.events_service,
        )

    #
    # CITY EVENTS BC
    #
    @cached_property
    def events_repository(self) -> AbstractEventsRepository:
        return EventsRepository(self.db_client)

    @cached_property
    def events_service(self) -> AbstractEventsService:
        return EventsService(self.events_repository, geocoding_client=self.here_client)

    #
    # CHAT BC
    #
    @cached_property
    def chat_repository(self) -> AbstractChatRepository:
        return ChatRepository(self.db_client)

    @cached_property
    def agent_runs_repository(self) -> AbstractAgentRunsRepository:
        return AgentRunsRepository(self.db_client)


_bootstrap: Bootstrap | None = None


def get_bootstrap() -> Bootstrap:
    global _bootstrap
    if _bootstrap is None:
        _bootstrap = Bootstrap(config)
    return _bootstrap


def get_bootstrap_dep() -> Bootstrap:
    """FastAPI dependency — resolves the process-wide container per request."""
    return get_bootstrap()


def get_auth_service_dep() -> "AbstractAuthService":
    """FastAPI dependency — the auth BC's service off the process container."""
    return get_bootstrap().auth_service
