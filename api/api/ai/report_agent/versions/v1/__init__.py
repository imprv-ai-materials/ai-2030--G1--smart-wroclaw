"""report_agent v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.report_agent.versions.v1.agent import ReportAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = ReportAgent

__all__ = ["ReportAgent", "AGENT"]
