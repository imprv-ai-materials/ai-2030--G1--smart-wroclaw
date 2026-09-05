"""triage_agent v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.triage_agent.versions.v1.agent import TriageAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = TriageAgent

__all__ = ["TriageAgent", "AGENT"]
