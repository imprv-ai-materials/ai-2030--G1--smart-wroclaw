"""Postgres LISTEN/NOTIFY bus — the cross-process bridge from the worker to the API.

The main agent runs on the WORKER (as an Inngest function); the WebSocket sockets
live in the API process. So the worker `publish()`es each step over a Postgres
NOTIFY, and the API runs `listen()` as a background task that relays every payload
to the in-memory `WebSocketManager`. One channel (`chat_progress`) carries the
conversation id inside the JSON payload — NOTIFY channel names are identifiers, and
a single channel keeps the API's LISTEN loop trivial.

No new infrastructure: it reuses the same Postgres the app already runs on. For
multiple API replicas, the same interface can be backed by Redis pub/sub instead.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

import psycopg
from loguru import logger

CHANNEL = "chat_progress"


class NotificationBus:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pub: psycopg.Connection | None = None

    def publish(self, payload: dict[str, Any]) -> None:
        """Fire one NOTIFY (best-effort; a dropped notify just means the UI falls
        back to fetching the finished message). Reuses one autocommit connection."""
        body = json.dumps(payload, ensure_ascii=False, default=str)
        try:
            if self._pub is None or self._pub.closed:
                self._pub = psycopg.connect(self._dsn, autocommit=True)
            self._pub.execute("SELECT pg_notify(%s, %s)", (CHANNEL, body))
        except Exception as exc:  # never let telemetry break a live turn
            logger.warning("NOTIFY failed: {}", exc)
            self._pub = None

    async def listen(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Block on `CHANNEL`, awaiting `handler(payload)` for each notification.
        Run this as a background task on the API process; it reconnects on error."""
        aconn = await psycopg.AsyncConnection.connect(self._dsn, autocommit=True)
        await aconn.execute(f"LISTEN {CHANNEL}")
        logger.info("chat progress bus: LISTEN {}", CHANNEL)
        async for note in aconn.notifies():
            try:
                await handler(json.loads(note.payload))
            except Exception as exc:
                logger.warning("chat progress handler error: {}", exc)
