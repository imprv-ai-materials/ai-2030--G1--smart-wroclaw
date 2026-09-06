"""guardrails v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.guardrails_agent.versions.v1.agent import GuardrailAgent

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = GuardrailAgent

__all__ = ["GuardrailAgent", "AGENT"]
