"""guardrails v2 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.guardrails_agent.versions.v2.agent import GuardrailAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = GuardrailAgent

__all__ = ["GuardrailAgent", "AGENT"]
