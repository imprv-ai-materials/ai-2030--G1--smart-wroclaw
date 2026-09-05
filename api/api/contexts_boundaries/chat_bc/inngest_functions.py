"""Durable / observable chat driver — one Inngest step per orchestrator element.

The synchronous path lives in `services/orchestrator.py::run_turn`; this wraps the
same elements in `ctx.step.run` so the pipeline is retried/memoized/traced when run
in the background (triggered by `smart_wroclaw/chat.turn`).
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

import inngest
from api.bootstrap import get_bootstrap
from api.contexts_boundaries.chat_bc.services.orchestrator import (
    _add_turn,
    _answer,
    _block_reply,
    _extract,
    _guard,
    _route,
    _search,
    build_search_reply,
)
from api.contexts_boundaries.city_events_bc.models import EventUnderstanding
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

    guard = await ctx.step.run("guardrails", lambda: _guard(text))
    if not guard["allow"]:
        return {"status": "blocked", "reason": guard["reason"], "reply": _block_reply(guard["reason"])}

    understanding = await ctx.step.run(
        "extract", lambda: _extract(bootstrap, text).model_dump(mode="json")
    )
    u = EventUnderstanding.model_validate(understanding)
    intent = await ctx.step.run("route", lambda: _route(text, u))

    if intent == "search":
        def _search_step() -> dict[str, Any]:
            filters, results = _search(bootstrap, u)
            return {
                "reply": build_search_reply(results),
                "filters": _jsonify(filters),
                "results": [e.model_dump(mode="json") for e in results],
            }

        payload = await ctx.step.run("search", _search_step)
        return {"status": "ok", "intent": "search", **payload}

    if intent == "add":
        payload = await ctx.step.run(
            "add", lambda: _jsonify(_add_turn(bootstrap, u))
        )
        return payload

    reply = await ctx.step.run("answer", lambda: _answer(bootstrap, text))
    return {"status": "ok", "intent": "answer", "reply": reply}


CHAT_INNGEST_FUNCTIONS = [chat_turn]
