"""The `ai/` layer's version resolver + `versions/current.yaml` pointers."""

import importlib

import pytest
from api.ai import load_current
from parameterized import param, parameterized
from tests import BaseUnitTestCase

# Every agent the composition root wires — the main agent plus its sub-agents.
AGENTS = [
    "main_agent",
    "guardrails_agent",
    "event_extractor",
    "router_agent",
    "search_agent",
    "report_agent",
    "analytics_agent",
    "geo_resolver",
]


class TestVersionResolver(BaseUnitTestCase):
    @parameterized.expand([param(name, agent=name) for name in AGENTS])
    def test_load_current__resolves_and_exposes_AGENT(self, _, agent) -> None:
        # GIVEN an agent with a versions/current.yaml
        # WHEN the current version is resolved
        current = load_current(agent)

        # THEN it points at a concrete class the version package exposes as AGENT
        assert current.version
        assert current.agent_class is not None
        module = importlib.import_module(f"api.ai.{agent}.versions.{current.version}")
        assert getattr(module, "AGENT", None) is current.agent_class

    def test_load_current__unknown_agent__raises(self) -> None:
        # GIVEN an agent name with no versions/ folder
        # WHEN / THEN resolving it surfaces a FileNotFoundError
        with pytest.raises(FileNotFoundError):
            load_current("nope_agent")
