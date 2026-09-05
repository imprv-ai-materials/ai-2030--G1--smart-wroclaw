"""The `ai/` layer's version resolver + `versions/current.yaml` pointers."""

import importlib

import pytest
from api.ai import load_current
from api.ai.assistant_agent import AbstractAssistantAgent
from parameterized import param, parameterized
from tests import BaseUnitTestCase


class TestVersionResolver(BaseUnitTestCase):
    def test_load_current__assistant__resolves_v1(self) -> None:
        # GIVEN / WHEN the current assistant version is resolved
        current = load_current("assistant_agent")

        # THEN it points at v1's concrete agent
        assert current.version == "v1"
        assert issubclass(current.agent_class, AbstractAssistantAgent)

    def test_load_current__unknown_agent__raises(self) -> None:
        # GIVEN an agent name with no versions/ folder
        # WHEN / THEN resolving it surfaces a FileNotFoundError
        with pytest.raises(FileNotFoundError):
            load_current("nope_agent")

    @parameterized.expand(
        [
            param("assistant v1", module_path="api.ai.assistant_agent.versions.v1"),
            param("assistant v2", module_path="api.ai.assistant_agent.versions.v2"),
        ]
    )
    def test_version_module__exposes_AGENT(self, _, module_path) -> None:
        # GIVEN a versions/<v> package
        # WHEN it is imported
        module = importlib.import_module(module_path)

        # THEN it exposes the `AGENT` the resolver relies on
        assert hasattr(module, "AGENT")

    def test_assistant_v2__subclasses_v1(self) -> None:
        # GIVEN the two assistant versions
        v1 = importlib.import_module("api.ai.assistant_agent.versions.v1").AGENT
        v2 = importlib.import_module("api.ai.assistant_agent.versions.v2").AGENT

        # THEN v2 is a distinct subclass of v1 (the "(from v1)" lineage)
        assert v2 is not v1
        assert issubclass(v2, v1)
