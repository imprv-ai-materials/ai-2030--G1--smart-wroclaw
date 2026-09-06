"""Durable / observable chat driver — runs one full turn in a retried Inngest step.

The synchronous path is `bootstrap.main_agent.run_turn(...)` (the composed main
agent). This background variant, triggered by `smart_wroclaw/chat.turn`, wraps the
same call in `ctx.step.run` so it is retried / memoized / traced. The per-element
breakdown now lives inside the main agent's sub-agents; hand the agent a step runner
if you later want each element (guard / extract / route / lane) traced separately.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

import inngest
from api.bootstrap import get_bootstrap
from api.inngest_app import EVENT_CHAT_TURN, inngest_client
from pydantic import BaseModel


def _jsonify(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    return value


@inngest_client.create_function(
    fn_id="chat-turn",
    trigger=inngest.TriggerEvent(event=EVENT_CHAT_TURN),
    retries=1,
)
async def chat_turn(ctx: inngest.Context) -> dict[str, Any]:
    text = str(ctx.event.data.get("text", ""))
    bootstrap = get_bootstrap()
    return await ctx.step.run("main-agent-turn", lambda: _jsonify(bootstrap.main_agent.run_turn(text)))


CHAT_INNGEST_FUNCTIONS = [chat_turn]
