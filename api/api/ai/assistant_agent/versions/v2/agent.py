"""assistant_agent · v2 (from v1).

Same pipeline as v1 — only the system prompt changes (tighter, answer-first, and
it reserves the 986 number for real emergencies). Subclassing v1 keeps the one
behavioural change (the prompt) obvious and inherits everything else. This is the
"(from v1)" lineage the versions/ folder encodes; a future v3 would subclass v2,
v4 subclass v3, and so on.
"""

from api.ai.assistant_agent.versions.v1.agent import AssistantAgent as AssistantAgentV1
from api.ai.assistant_agent.versions.v2.prompts import SYSTEM_PROMPT


class AssistantAgent(AssistantAgentV1):
    def __init__(self, openai_client, model=None, system_prompt=SYSTEM_PROMPT):
        super().__init__(openai_client, model=model, system_prompt=system_prompt)
