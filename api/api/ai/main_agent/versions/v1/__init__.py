"""main_agent v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.main_agent.versions.v1.agent import MainAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = MainAgent

__all__ = ["MainAgent", "AGENT"]
