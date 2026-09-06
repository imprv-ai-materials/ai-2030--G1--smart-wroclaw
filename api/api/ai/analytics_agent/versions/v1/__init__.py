"""analytics_agent v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.analytics_agent.versions.v1.agent import AnalyticsAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = AnalyticsAgent

__all__ = ["AnalyticsAgent", "AGENT"]
