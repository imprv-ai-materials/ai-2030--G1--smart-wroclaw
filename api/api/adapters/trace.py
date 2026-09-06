"""Per-turn agent trace — a contextvar-scoped record of what the main agent did.

The main agent calls `begin()` at the top of a turn, then `add(...)` once per
component it runs (with a short input/output summary); the OpenAI client calls
`record_llm(...)` on every model call so each component's token cost + model land
on the step it happened in. `collect()` returns the whole trace, which the chat API
attaches to the assistant reply — shown only to ADMIN users.

It's contextvar-scoped so concurrent requests don't collide, and a no-op when no
trace is active (so agents run identically under the eval harness / tests).
"""

from __future__ import annotations

import contextvars
import json
from typing import Any

_LLM: contextvars.ContextVar[list | None] = contextvars.ContextVar("_agent_trace_llm", default=None)
_STEPS: contextvars.ContextVar[list | None] = contextvars.ContextVar("_agent_trace_steps", default=None)


def begin() -> None:
    """Start a fresh trace for this turn (call once, before any component runs)."""
    _LLM.set([])
    _STEPS.set([])


def active() -> bool:
    return _STEPS.get() is not None


def record_llm(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record one model call's usage (called by the OpenAI client)."""
    calls = _LLM.get()
    if calls is not None:
        calls.append({"model": model, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens})


def mark() -> int:
    """Snapshot the LLM-call count, so `add(..., since=mark())` attributes only the
    calls a component made to that component."""
    return len(_LLM.get() or [])


def add(component: str, *, input: Any = None, output: Any = None, since: int = 0) -> None:
    """Record one component step + the model calls it made since `since`."""
    steps = _STEPS.get()
    if steps is None:
        return
    calls = (_LLM.get() or [])[since:]
    steps.append(
        {
            "component": component,
            "input": _short(input),
            "output": _short(output),
            "models": sorted({c["model"] for c in calls}),
            "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
            "completion_tokens": sum(c["completion_tokens"] for c in calls),
            "llm_calls": len(calls),
        }
    )


def collect() -> dict[str, Any]:
    """The whole trace: the ordered steps + turn totals."""
    steps = _STEPS.get() or []
    return {
        "steps": steps,
        "llm_calls": sum(s["llm_calls"] for s in steps),
        "prompt_tokens": sum(s["prompt_tokens"] for s in steps),
        "completion_tokens": sum(s["completion_tokens"] for s in steps),
        "total_tokens": sum(s["prompt_tokens"] + s["completion_tokens"] for s in steps),
    }


def _short(value: Any, limit: int = 320) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    return value if len(value) <= limit else value[:limit] + "…"
