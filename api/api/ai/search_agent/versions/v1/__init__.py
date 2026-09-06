"""search_agent v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.search_agent.versions.v1.agent import SearchAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = SearchAgent

__all__ = ["SearchAgent", "AGENT"]
