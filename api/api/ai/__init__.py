"""The AI layer — one folder per agent, each holding its contract, versioned
implementations, datasets and evaluations.

Layout, per agent:

    ai/<agent_name>/
        base.py             # Abstract<Agent> — the contract the domain depends on
        datasets/           # inputs used to evaluate the agent   (dev-only)
        evaluations/        # eval definitions / expected outcomes (dev-only)
        versions/
            v1/ v2/ ...     # concrete versions: agent.py + prompts.py; each exports AGENT
            current.yaml    # names the ACTIVE version (the loader resolves it)

Agent *code* lives here (moved out of each bounded context's `agents_bc`); the
domain services depend only on the `base.py` contract, and `bootstrap.agents`
wires the CURRENT concrete version via `load_current`. Structure mirrors the
reference `imprv-ai-service` `agents_bc`.
"""

from api.ai.loader import CurrentVersion, load_current

__all__ = ["CurrentVersion", "load_current"]
