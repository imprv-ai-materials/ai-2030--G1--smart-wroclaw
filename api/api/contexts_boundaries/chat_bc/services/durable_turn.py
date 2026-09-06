"""The durable chat turn — the main agent decomposed into steps.

`run_turn_durable(bootstrap, data, step)` runs one turn as a sequence of steps:
guardrails → extractor → router → geo → lane. It's parameterised by a `step`
runner so the SAME code drives two callers:

  • the Inngest worker passes `ctx.step.run` → each component is a real, retriable
    Inngest step, visible in the Runs panel;
  • a test passes a passthrough (`lambda _id, fn: fn()`) → runs inline, no Inngest.

Every step, as it completes, writes an `agent_run_steps` row and fires a NOTIFY
(`chat_progress`) that the API relays to the resident's WebSocket. On finish it
fills the pending assistant message + finalizes the run. Token/model usage per step
is captured via the `trace` contextvar (reset inside each step so it's thread-safe).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from api.adapters import trace
from api.ai.main_agent.versions.v1.agent import (
    block_reply,
    build_ready_reply,
    build_report_reply,
    build_search_reply,
)
from api.contexts_boundaries.chat_bc.models import RunStatus
from api.contexts_boundaries.city_events_bc.models import (
    EventUnderstanding,
    coerce_draft_for_create,
    to_search_filters,
)

StepRunner = Callable[[str, Callable[[], Any]], Awaitable[Any]]

_RESULTS_CAP = 20  # how many event cards to persist on the message


def _short(value: Any, limit: int = 320) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, str):
        import json

        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    return value if len(value) <= limit else value[:limit] + "…"


def _trunc(value: Any, limit: int = 320) -> Any:
    """Cap long strings but keep structured values intact (they're stored as JSONB)."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


async def run_turn_durable(bootstrap, data: dict[str, Any], step: StepRunner) -> dict[str, Any]:
    conv_id = int(data["conversation_id"])
    message_id = int(data["message_id"])
    run_id = int(data["run_id"])
    text = str(data.get("text") or "")
    fields = data.get("fields")
    action = data.get("action")
    prior_draft = data.get("prior_draft")
    reporter_id = data.get("reporter_id")
    reporter_confirmed = bool(data.get("reporter_confirmed"))

    runs = bootstrap.agent_runs_repository
    chat = bootstrap.chat_repository
    bus = bootstrap.notification_bus

    def publish(payload: dict[str, Any]) -> None:
        bus.publish({"conversation_id": conv_id, "message_id": message_id, "run_id": run_id, **payload})

    def record(seq: int, component: str, *, input: Any, output: Any, usage: dict) -> None:
        models = usage.get("models", [])
        pt, ct = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        runs.add_step(
            run_id,
            seq,
            component,
            input=_trunc(input),
            output=_trunc(output),
            models=models,
            prompt_tokens=pt,
            completion_tokens=ct,
        )
        publish(
            {
                "type": "step",
                "seq": seq,
                "component": component,
                "output": _short(output),
                "models": models,
                "prompt_tokens": pt,
                "completion_tokens": ct,
            }
        )

    history = _history(chat, conv_id, message_id)

    async def finalize(result: dict[str, Any]) -> dict[str, Any]:
        full = runs.get_run(run_id)
        pt = sum(s.prompt_tokens for s in full.steps) if full else 0
        ct = sum(s.completion_tokens for s in full.steps) if full else 0
        trace_summary = {
            "steps": [
                {
                    "component": s.component,
                    "output": _short(s.output),
                    "models": s.models,
                    "prompt_tokens": s.prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "llm_calls": 1 if s.models else 0,
                }
                for s in (full.steps if full else [])
            ],
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "llm_calls": sum(1 for s in (full.steps if full else []) if s.models),
        }
        chat.update_message(message_id, result.get("reply", ""), _message_data(result, trace_summary))
        runs.finalize_run(
            run_id,
            message_id=message_id,
            status=RunStatus.DONE,
            intent=result.get("intent"),
            prompt_tokens=pt,
            completion_tokens=ct,
        )
        publish({"type": "done"})
        return result

    # -- a pure confirm/commit turn (no text to guard/extract/route) -----------
    if action == "confirm":
        return await finalize(_confirm_turn(bootstrap, prior_draft, reporter_id, reporter_confirmed, record))

    has_fields = bool(fields)

    def guardrails_work() -> dict:
        trace.begin()
        verdict = bootstrap.guardrails_agent.check(text, history)
        record(
            1,
            "guardrails_agent",
            input=text,
            output={"allow": verdict.allow, "reason": verdict.reason},
            usage=trace.usage(),
        )
        return {"allow": verdict.allow, "reason": verdict.reason}

    verdict = await step("guardrails", guardrails_work)
    if not verdict["allow"] and not has_fields:
        return await finalize(
            {"status": "blocked", "reason": verdict["reason"], "reply": block_reply(verdict["reason"]), "intent": None}
        )

    def extract_work() -> dict:
        trace.begin()
        u = bootstrap.event_extractor.extract(text, history=history)
        d = u.model_dump(mode="json")
        record(
            2,
            "event_extractor",
            input=text,
            output={"type": d.get("type"), "category": d.get("category"), "district": d.get("district")},
            usage=trace.usage(),
        )
        return d

    u = EventUnderstanding.model_validate(await step("extract", extract_work))

    if has_fields:
        intent = "report"
    else:

        def route_work() -> str:
            trace.begin()
            decision = bootstrap.router_agent.route(text, u, history)
            record(3, "router_agent", input=text, output={"intent": decision.intent.value}, usage=trace.usage())
            return decision.intent.value

        intent = await step("route", route_work)

    if intent == "report":
        return await finalize(await step("report", lambda: _report_lane(bootstrap, u, fields, prior_draft, record)))

    def geo_work() -> dict | None:
        trace.begin()
        # Only the EXTRACTED location — never the raw query, or HERE fuzzily geocodes
        # a whole question to the Wrocław centroid + a 1.5 km radius (→ search finds 0).
        hint = u.location_text or u.address or u.district
        resolved = bootstrap.geo_resolver.resolve(hint) if hint else None
        scope = None
        if resolved is not None and not resolved.needs_user_location:
            scope = {
                "district": resolved.district,
                "lat": resolved.lat,
                "lng": resolved.lng,
                "radius_m": resolved.radius_m,
            }
        record(4, "geo_resolver", input=hint, output=scope, usage=trace.usage())
        return scope

    scope = await step("geo", geo_work)
    if intent == "analytics":
        return await finalize(await step("analytics", lambda: _analytics_lane(bootstrap, u, scope, record)))
    return await finalize(await step("search", lambda: _search_lane(bootstrap, u, scope, record)))


# -- lanes (each records its own step + returns a JSON-serialisable result) -----
def _search_lane(b, u: EventUnderstanding, scope, record) -> dict[str, Any]:
    trace.begin()
    results = b.search_agent.search(u, scope=scope)
    record(
        5,
        "search_agent",
        input={"filters": to_search_filters(u), "scope": scope},
        output=f"{len(results)} events",
        usage=trace.usage(),
    )
    return {
        "status": "ok",
        "intent": "search",
        "reply": build_search_reply(results),
        "filters": to_search_filters(u),
        "results": [e.model_dump(mode="json") for e in results[:_RESULTS_CAP]],
    }


def _analytics_lane(b, u: EventUnderstanding, scope, record) -> dict[str, Any]:
    trace.begin()
    answer = b.analytics_agent.answer(u, scope=scope)
    record(
        5,
        "analytics_agent",
        input={"filters": to_search_filters(u), "scope": scope},
        output={"count": answer.count, "breakdown": answer.breakdown},
        usage=trace.usage(),
    )
    return {
        "status": "ok",
        "intent": "analytics",
        "reply": answer.reply,
        "count": answer.count,
        "breakdown": answer.breakdown,
    }


def _report_lane(b, u: EventUnderstanding, fields, prior_draft, record) -> dict[str, Any]:
    trace.begin()
    turn = b.report_agent.plan_turn(u, prior_draft=prior_draft, fields=fields)
    record(
        4,
        "report_agent",
        input={"prior_draft": prior_draft, "fields": fields},
        output={"missing_fields": turn.missing_fields, "ready": turn.ready},
        usage=trace.usage(),
    )
    if turn.missing_fields:
        return {
            "status": "ok",
            "intent": "report",
            "reply": build_report_reply(turn.draft, turn.missing_fields),
            "draft": turn.draft,
            "missing_fields": turn.missing_fields,
            "form": turn.form,
        }
    return {
        "status": "ok",
        "intent": "report",
        "reply": build_ready_reply(turn.draft, turn.duplicates),
        "draft": turn.draft,
        "missing_fields": [],
        "ready": True,
        "duplicates": [e.model_dump(mode="json") for e in turn.duplicates[:_RESULTS_CAP]],
    }


def _confirm_turn(b, prior_draft, reporter_id, reporter_confirmed, record) -> dict[str, Any]:
    draft = prior_draft or {}
    trace.begin()
    turn = b.report_agent.plan_turn(EventUnderstanding(), prior_draft=draft)
    record(
        1,
        "report_agent",
        input={"prior_draft": draft},
        output={"missing_fields": turn.missing_fields, "ready": turn.ready},
        usage=trace.usage(),
    )
    if turn.missing_fields:
        return {
            "status": "ok",
            "intent": "report",
            "reply": "Zanim dodam zgłoszenie, uzupełnij brakujące pola.",
            "draft": turn.draft,
            "missing_fields": turn.missing_fields,
            "form": turn.form,
        }
    if reporter_id is None:
        return {
            "status": "login_required",
            "intent": "report",
            "reply": "Aby dodać zgłoszenie, zaloguj się na swoje konto.",
            "draft": draft,
            "ready": True,
        }
    if not reporter_confirmed:
        return {
            "status": "email_unconfirmed",
            "intent": "report",
            "reply": "Potwierdź adres e-mail, aby móc dodawać zgłoszenia.",
            "draft": draft,
            "ready": True,
        }
    trace.begin()
    typed = coerce_draft_for_create(draft)
    where = typed.get("address") or typed.get("location_text") or typed.get("district")
    point = b.geo_resolver.resolve(where) if where else None
    event = b.events_service.create_event(
        type_=typed["type_"],
        title=typed["title"],
        description=typed["description"],
        reporter_id=reporter_id,
        category=typed.get("category"),
        severity=typed.get("severity"),
        subtype=typed.get("subtype"),
        location_text=typed.get("location_text"),
        address=typed.get("address"),
        district=typed.get("district") or (point.district if point else None),
        lat=point.lat if point else None,
        lng=point.lng if point else None,
        starts_at=typed.get("starts_at"),
        ends_at=typed.get("ends_at"),
    )
    record(
        2,
        "events_service.create",
        input={"district": event.district},
        output={"id": event.id, "title": event.title},
        usage=trace.usage(),
    )
    return {
        "status": "ok",
        "intent": "report",
        "reply": f"✅ Dodano zgłoszenie: **{event.title}**. Dziękujemy!",
        "created": event.model_dump(mode="json"),
    }


def _history(chat, conv_id: int, message_id: int) -> list[dict[str, str]]:
    """Prior turns (excluding the empty pending assistant message), each carrying
    its intent so the router can continue a report flow."""
    out: list[dict[str, str]] = []
    for m in chat.list_messages(conv_id, limit=20):
        if m.id == message_id or not m.content:
            continue
        out.append({"role": m.role.value, "content": m.content, "intent": (m.data or {}).get("intent")})
    return out


def _message_data(result: dict[str, Any], trace_summary: dict) -> dict[str, Any]:
    created = result.get("created")
    return {
        "intent": result.get("intent"),
        "status": result.get("status"),
        "filters": result.get("filters"),
        "results": result.get("results"),
        "missing_fields": result.get("missing_fields"),
        "draft": result.get("draft"),
        "form": result.get("form"),
        "ready": result.get("ready"),
        "duplicates": result.get("duplicates"),
        "count": result.get("count"),
        "breakdown": result.get("breakdown"),
        "created": created,
        "created_event_id": created.get("id") if isinstance(created, dict) else None,
        "geocode": bool(created) and not (created.get("lat") if isinstance(created, dict) else True),
        "trace": trace_summary,
    }
