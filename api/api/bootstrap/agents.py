"""Agent factories — the one place that turns config into a live agent.

They sit between the DI container (`Bootstrap`) and the versioned agent code under
`api/ai/`, so that *which version* an agent runs is resolved in exactly one spot.
`load_current` reads `ai/<agent>/versions/current.yaml`, imports the named version
and hands back its concrete `AGENT` class; the factory constructs it with the
shared clients / repos + config. Promoting a version is a one-line YAML edit.

The `get_<agent>()` naming mirrors the composition-root convention: ask for an
agent by name and get the CURRENT wiring back. `main_agent` is composed straight
in `Bootstrap` (it needs every sub-agent), so it has no factory here.
"""

from api.adapters.geocoding import HereGeocodingClient
from api.adapters.llm import OpenAIClient
from api.ai import load_current
from api.ai.analytics_agent import AbstractAnalyticsAgent
from api.ai.event_extractor import AbstractEventExtractor
from api.ai.geo_resolver import AbstractGeoResolver
from api.ai.guardrails_agent import AbstractGuardrailAgent
from api.ai.report_agent import AbstractReportAgent
from api.ai.router_agent import AbstractRouterAgent
from api.ai.search_agent import AbstractSearchAgent
from api.config import Config
from api.contexts_boundaries.city_events_bc.repositories import AbstractEventsRepository


def get_event_extractor(openai_client: OpenAIClient, config: Config) -> AbstractEventExtractor:
    current = load_current("event_extractor")
    return current.agent_class(openai_client, model=current.model or config.openai.default_model_name)


def get_guardrails_agent(openai_client: OpenAIClient, config: Config) -> AbstractGuardrailAgent:
    current = load_current("guardrails_agent")
    return current.agent_class(openai_client, model=current.model or config.openai.default_model_name)


def get_router_agent(openai_client: OpenAIClient, config: Config) -> AbstractRouterAgent:
    current = load_current("router_agent")
    return current.agent_class(openai_client, model=current.model or config.openai.default_model_name)


def get_search_agent(events_repository: AbstractEventsRepository) -> AbstractSearchAgent:
    # Deterministic — depends only on the events repo (ranking, no model).
    current = load_current("search_agent")
    return current.agent_class(events_repository)


def get_report_agent(events_repository: AbstractEventsRepository) -> AbstractReportAgent:
    # Deterministic — draft completion + dedup over the events repo (no model).
    current = load_current("report_agent")
    return current.agent_class(events_repository)


def get_analytics_agent(
    events_repository: AbstractEventsRepository, openai_client: OpenAIClient, config: Config
) -> AbstractAnalyticsAgent:
    # Deterministic count; the model (when keyed) only phrases the sentence.
    current = load_current("analytics_agent")
    return current.agent_class(
        events_repository, openai_client=openai_client, model=current.model or config.openai.default_model_name
    )


def get_geo_resolver(geocoding_client: HereGeocodingClient) -> AbstractGeoResolver:
    current = load_current("geo_resolver")
    return current.agent_class(geocoding_client)
