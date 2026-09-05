"""Offline assistant fallback — when no OpenAI key is configured the agent must
still return a usable, clearly-labelled answer. Pure unit test.
"""

from api.adapters.llm import OpenAIClient
from api.ai.assistant_agent.versions.v1.agent import AssistantAgent
from tests import BaseUnitTestCase


class TestAssistantAgentOfflineAnswer(BaseUnitTestCase):
    def test_answer__offline__flags_offline_mode_and_echoes_question(self) -> None:
        # GIVEN an assistant agent with no OpenAI key
        agent = AssistantAgent(OpenAIClient(api_key=None))

        # WHEN a citizen asks a maintenance question
        answer = agent.answer("Kiedy wywóz odpadów zmieszanych?")

        # THEN the reply flags offline mode and echoes the question back
        assert "offline" in answer.lower()
        assert "Kiedy wywóz odpadów zmieszanych?" in answer
