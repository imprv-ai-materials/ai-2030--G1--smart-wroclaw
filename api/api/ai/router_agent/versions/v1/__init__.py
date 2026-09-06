"""router v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.router_agent.versions.v1.agent import RouterAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = RouterAgent

__all__ = ["RouterAgent", "AGENT"]
