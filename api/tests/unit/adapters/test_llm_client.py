"""OpenAI client configuration flag — gates the offline fallbacks across the AI
agents.
"""

from api.adapters.llm import OpenAIClient
from tests import BaseUnitTestCase


class TestOpenAIClientConfiguration(BaseUnitTestCase):
    def test_is_configured__no_api_key__is_false(self) -> None:
        # GIVEN a client built without an API key (local dev / CI)
        client = OpenAIClient(api_key=None)

        # WHEN / THEN it reports itself unconfigured, enabling offline fallbacks
        assert client.is_configured is False
