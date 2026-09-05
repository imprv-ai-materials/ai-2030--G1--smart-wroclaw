"""assistant_agent v2 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.assistant_agent.versions.v2.agent import AssistantAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = AssistantAgent

__all__ = ["AssistantAgent", "AGENT"]
