"""Shared Inngest client + event names.

Lives in its own module so both the FastAPI app (`api.py`, which serves the
functions on the worker role) and the REST routers (which only *send* events)
import the same client without a circular import through `api.py`.

Event names are the single source of truth for the async seams:

    smart_wroclaw/assistant.run     a citizen asked a question → answer it
    smart_wroclaw/report.triage     a citizen filed a report   → AI-triage it

Both are fire-and-forget from the API; the heavy work (LLM calls) runs on the
worker process so a burst of triage/answer jobs can't starve interactive
traffic.
"""

import os

import inngest
from loguru import logger

# Local dev talks to the Inngest dev server (compose.yaml), which needs no
# signing key. Real deployments set SMART_WROCLAW_ENV=production so the client
# switches to cloud mode and requires INNGEST_SIGNING_KEY / INNGEST_EVENT_KEY.
_IS_PRODUCTION = os.environ.get("SMART_WROCLAW_ENV", "dev").lower() in ("prod", "production")

inngest_client = inngest.Inngest(
    app_id="smart-wroclaw",
    logger=logger,
    is_production=_IS_PRODUCTION,
)

EVENT_ASSISTANT_RUN = "smart_wroclaw/assistant.run"
EVENT_REPORT_TRIAGE = "smart_wroclaw/report.triage"
# An event's location string was added/changed → resolve its lat/lng via HERE.
EVENT_EVENT_GEOCODE = "smart_wroclaw/event.geocode"
# A chat message → the orchestrator ("main agent") composes the tool elements.
EVENT_CHAT_TURN = "smart_wroclaw/chat.turn"
