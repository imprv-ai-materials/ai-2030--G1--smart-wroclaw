"""In-process WebSocket connection manager.

Lets the app *push* live status to connected UI clients — assistant run progress,
report state changes — instead of the client polling. It complements, and does
not replace, the polling fallback in `ui/hooks/use-run-poll.ts`: if no socket is
connected, publishes are simply dropped and the UI still converges via polling.

Clients subscribe by a **topic** string (e.g. a conversation id); `publish()`
fans a JSON message out to every socket on that topic. Deliberately in-memory and
single-process — correct for local dev and a single API replica. For multiple
replicas, back the same interface with Redis pub/sub.
"""

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._topics: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, topic: str, websocket: WebSocket) -> None:
        """Accept the socket and subscribe it to `topic`."""
        await websocket.accept()
        async with self._lock:
            self._topics[topic].add(websocket)

    async def disconnect(self, topic: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._topics[topic].discard(websocket)
            if not self._topics[topic]:
                self._topics.pop(topic, None)

    async def publish(self, topic: str, message: dict) -> None:
        """Fan `message` out to every socket on `topic`; drop ones that error."""
        async with self._lock:
            sockets = list(self._topics.get(topic, ()))

        dead: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(message)
            except Exception:  # client vanished mid-send — prune it below
                dead.append(websocket)

        if dead:
            async with self._lock:
                topic_sockets = self._topics.get(topic)
                if topic_sockets is not None:
                    for websocket in dead:
                        topic_sockets.discard(websocket)
                    if not topic_sockets:
                        self._topics.pop(topic, None)

    @property
    def topic_count(self) -> int:
        """Number of topics with at least one live subscriber (health/debug)."""
        return len(self._topics)
