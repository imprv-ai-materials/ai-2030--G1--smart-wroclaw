"""Composition root for the eval harness — the DI container every agent's
`eval/` scripts resolve against, mirroring `api/api/bootstrap` for the service.

Each eval used to re-do the same wiring by hand: load `Config`, build an
`OpenAIClient`, resolve the CURRENT agent version and construct it, stand up an
`EventsService`. That lived copy-pasted across `event_extractor/eval/run_deepeval.py`,
`main_agent/eval/run_eval.py`, … so "which client / which version / which offline
toggle" had no single home. This is that home, next to the agent code it wires.

Same shape as the service container: each dependency is a lazily-built
`cached_property` (nothing touches OpenAI until first use), plus `build_*`
factories for the bits the evals parameterise — the offline↔LLM toggle and the
corpus-backed repository. `get_bootstrap()` hands back a process-wide singleton.

Two deliberate differences from `api/api/bootstrap`, both because an eval must run
offline with zero credentials:

  * `Config` is loaded **lazily** (`config` cached_property), so a purely offline
    eval that only calls `build_events_service()` never imports `api.config` — and
    therefore never needs the Postgres env vars its `Config()` demands. The
    main_agent retrieval eval keeps its "no API key, no Postgres, no cost" promise.
    (This is also why it's a standalone module, not part of the `api.bootstrap`
    package, whose `__init__` eagerly imports `api.config` + the full service tree.)
  * There are two OpenAI clients: `offline_openai_client` (no key → the agents'
    deterministic keyword path, the baseline the evals score) and
    `llm_openai_client` (the real key). `build_*(use_llm=...)` picks between them.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from api.adapters.llm import OpenAIClient
from api.ai import load_current
from api.ai.event_extractor import AbstractEventExtractor
from api.contexts_boundaries.city_events_bc.repositories import AbstractEventsRepository
from api.contexts_boundaries.city_events_bc.services import AbstractEventsService, EventsService

if TYPE_CHECKING:  # `api.config` is imported lazily at runtime (see `config`).
    from api.config import Config


class Bootstrap:
    """Lazily wires the eval harness's config, clients, agents and services.

    Construct with no argument to resolve against the process `Config`, or pass an
    explicit one (handy in tests). Nothing is built — and `api.config` is not even
    imported — until a property that needs it is first read.
    """

    def __init__(self, config: "Config | None" = None) -> None:
        self._config_override = config

    @cached_property
    def config(self) -> "Config":
        # Imported here, not at module top, so an offline eval that never touches a
        # config-dependent path (e.g. one using only `build_events_service`) does
        # not instantiate `Config()` — which would demand the Postgres env vars.
        if self._config_override is not None:
            return self._config_override
        from api.config import config as process_config

        return process_config

    #
    # clients — the offline client (no key) is the deterministic default the evals
    # score against; the LLM client is the real OpenAI path (the `--llm` flag).
    #
    @cached_property
    def offline_openai_client(self) -> OpenAIClient:
        """No API key → `is_configured` is False, so the agents take their offline
        keyword heuristic (no network, no cost, deterministic). This is the
        baseline every eval reports against."""
        return OpenAIClient(api_key=None, default_model_name=self.config.openai.default_model_name)

    @cached_property
    def llm_openai_client(self) -> OpenAIClient:
        return OpenAIClient(
            api_key=self.config.openai.api_key,
            default_model_name=self.config.openai.default_model_name,
        )

    def build_openai_client(self, use_llm: bool = False) -> OpenAIClient:
        """The client an eval should run against. `use_llm=False` (default) is the
        offline baseline; `use_llm=True` is the real OpenAI path — which still
        degrades to offline if no key is configured (`is_configured` is False)."""
        return self.llm_openai_client if use_llm else self.offline_openai_client

    #
    # agents — resolved at the CURRENT version (`ai/<agent>/versions/current.yaml`),
    # exactly like `api/bootstrap.agents`, so an eval scores whatever actually
    # ships. Promoting a version is a one-line YAML edit, never a change here.
    #
    def build_event_extractor(self, use_llm: bool = False) -> AbstractEventExtractor:
        current = load_current("event_extractor")
        model = current.model or self.config.openai.default_model_name
        return current.agent_class(self.build_openai_client(use_llm), model=model)

    @staticmethod
    def current_version(agent_name: str) -> str:
        """The CURRENT version tag of an agent (e.g. "v1") — what an eval prints in
        its report so a score is always attributable to a concrete version."""
        return load_current(agent_name).version

    #
    # services — the REAL search code path (`EventsService.list_events`) over an
    # in-memory, corpus-backed repository, so the retrieval eval scores production
    # ranking/matching offline. No geocoder: retrieval never needs coordinates.
    #
    def build_events_service(self, repository: AbstractEventsRepository) -> AbstractEventsService:
        return EventsService(repository)


_bootstrap: Bootstrap | None = None


def get_bootstrap() -> Bootstrap:
    global _bootstrap
    if _bootstrap is None:
        _bootstrap = Bootstrap()
    return _bootstrap


def get_config() -> "Config":
    return get_bootstrap().config
