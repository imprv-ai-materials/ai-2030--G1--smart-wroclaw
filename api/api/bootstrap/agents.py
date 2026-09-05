"""Agent factories — the one place that turns config into a live agent.

They sit between the DI container (`Bootstrap`) and the versioned agent code
under `api/ai/`, so that *which version* an agent runs is resolved in exactly one
spot. `load_current` reads `ai/<agent>/versions/current.yaml`, imports the named
version and hands back its concrete `AGENT` class; the factory constructs it with
the shared clients + config (the version supplies its own prompt). Promoting a
version is a one-line YAML edit — never a code change here.

The `get_<agent>()` naming mirrors the composition-root convention: ask for an
agent by name and get the CURRENT wiring back.
"""

from api.adapters.llm import OpenAIClient
from api.ai import load_current
from api.ai.assistant_agent import AbstractAssistantAgent
from api.ai.event_extractor import AbstractEventExtractor
from api.ai.triage_agent import AbstractTriageAgent
from api.config import Config


def get_assistant_agent(openai_client: OpenAIClient, config: Config) -> AbstractAssistantAgent:
    current = load_current("assistant_agent")
    return current.agent_class(openai_client, model=current.model or config.assistant.model)


def get_event_extractor(openai_client: OpenAIClient, config: Config) -> AbstractEventExtractor:
    current = load_current("event_extractor")
    # No dedicated config knob yet: fall back to the shared OpenAI default model.
    return current.agent_class(openai_client, model=current.model or config.openai.default_model_name)


def get_triage_agent(openai_client: OpenAIClient, config: Config) -> AbstractTriageAgent:
    current = load_current("triage_agent")
    return current.agent_class(
        openai_client,
        model=current.model or config.reports.triage_model,
        default_department=config.reports.default_department,
    )
