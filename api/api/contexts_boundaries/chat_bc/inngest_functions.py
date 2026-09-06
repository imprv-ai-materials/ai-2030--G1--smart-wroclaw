"""Durable chat driver — the main agent, run as an Inngest function on the worker.

Triggered by `smart_wroclaw/chat.turn` (published by POST /chat/turn). The turn's
components run as `ctx.step.run` steps — guardrails → extract → route → geo → lane —
so each is a real, retriable, traced Inngest step. Each step also writes an
`agent_run_steps` row and fires a NOTIFY the API relays to the resident's WebSocket.
The orchestration lives in `services/durable_turn.py` (shared with a sync test driver).
"""

from typing import Any, Callable

import inngest
from api.bootstrap import get_bootstrap
from api.contexts_boundaries.chat_bc.services.durable_turn import run_turn_durable
from api.inngest_app import EVENT_CHAT_TURN, inngest_client


@inngest_client.create_function(
    fn_id="chat-turn",
    trigger=inngest.TriggerEvent(event=EVENT_CHAT_TURN),
    retries=1,
)
async def chat_turn(ctx: inngest.Context) -> dict[str, Any]:
    async def step(step_id: str, fn: Callable[[], Any]) -> Any:
        return await ctx.step.run(step_id, fn)

    result = await run_turn_durable(get_bootstrap(), ctx.event.data, step)
    # The full result is streamed to the UI over the WebSocket; the function's own
    # return is just a compact summary for the Inngest Runs panel.
    return {"status": result.get("status"), "intent": result.get("intent")}


CHAT_INNGEST_FUNCTIONS = [chat_turn]
