"""FastAPI entrypoint — runs in one of three roles (env `SMART_WROCLAW_ROLE`).

The same app powers both the user-facing REST API and the Inngest worker;
which surfaces get mounted is decided by the role so a burst of background jobs
(chat turns, HERE geocoding) on the worker can't starve the uvicorn workers
serving interactive `/api/v1` traffic.

    SMART_WROCLAW_ROLE=api     → REST routers only            (default port 8101)
    SMART_WROCLAW_ROLE=worker  → /api/inngest function host   (default port 8103)
    SMART_WROCLAW_ROLE=all     → both (single-process dev / back-compat)

Locally the Inngest dev server (compose.yaml) points at the worker's
/api/inngest; the REST role only ever `inngest_client.send(...)`s events.
"""

import os

import inngest.fast_api
from api.bootstrap import get_bootstrap
from api.contexts_boundaries.auth_bc.router import auth_router
from api.contexts_boundaries.chat_bc.inngest_functions import CHAT_INNGEST_FUNCTIONS
from api.contexts_boundaries.chat_bc.router import chat_router
from api.contexts_boundaries.city_events_bc.inngest_functions import EVENTS_INNGEST_FUNCTIONS
from api.contexts_boundaries.city_events_bc.router import events_router
from api.inngest_app import inngest_client
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Eagerly build the container so misconfiguration fails fast at boot.
bootstrap = get_bootstrap()

API_PREFIX = "/api/v1"

ROLE = os.environ.get("SMART_WROCLAW_ROLE", "all").lower()
SERVE_REST = ROLE in ("api", "all")
SERVE_WORKER = ROLE in ("worker", "all")


app = FastAPI(
    title="Smart Wrocław API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@app.get("/")
async def root() -> dict:
    """Health/identity — probed by the container health-check on both roles."""
    return {"service": "smart-wroclaw", "role": ROLE}


#
# WORKER — Inngest function host. Only mounted in worker/all so the API process
# never executes a long-running AI job.
#
if SERVE_WORKER:
    inngest.fast_api.serve(
        app,
        inngest_client,
        [
            *EVENTS_INNGEST_FUNCTIONS,
            *CHAT_INNGEST_FUNCTIONS,
        ],
        serve_path="/api/inngest",
    )


#
# API — REST layer for the Next.js UI. These endpoints only persist + send
# Inngest events; the heavy execution happens on the worker.
#
if SERVE_REST:
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(events_router, prefix=API_PREFIX)
    app.include_router(chat_router, prefix=API_PREFIX)

    @app.websocket("/ws/{topic}")
    async def ws_topic(websocket: WebSocket, topic: str) -> None:
        """Live push channel for a topic (e.g. a conversation id).

        The UI subscribes here for run/report updates; polling
        (`use-run-poll.ts`) remains the fallback if the socket drops. Inbound
        frames are ignored — this is a one-way server→client stream + keepalive.
        """
        manager = bootstrap.websocket_manager
        await manager.connect(topic, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(topic, websocket)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
