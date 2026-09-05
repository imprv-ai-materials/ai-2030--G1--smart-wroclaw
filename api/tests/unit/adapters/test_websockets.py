"""WebSocket connection-manager adapter + the /ws/{topic} route.

The manager tests are `async def` methods on `BaseUnitTestCase` — no decorator
needed, `IsolatedAsyncioTestCase` runs them. The route smoke test is a plain
function using the FastAPI TestClient (the /ws route is mounted because
`tests/__init__` pins `SMART_WROCLAW_ROLE=api`).
"""

from fastapi.testclient import TestClient
from tests import BaseUnitTestCase


class FakeWebSocket:
    """Minimal stand-in for a Starlette WebSocket used by the manager."""

    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self._fail_on_send:
            raise RuntimeError("client gone")
        self.sent.append(message)


class TestWebSocketManager(BaseUnitTestCase):
    def _manager(self):
        from api.adapters.websockets import WebSocketManager

        return WebSocketManager()

    async def test_connect_and_publish__fans_out_to_all_sockets(self) -> None:
        # GIVEN two sockets subscribed to the same topic
        manager = self._manager()
        a, b = FakeWebSocket(), FakeWebSocket()
        await manager.connect("conv:1", a)
        await manager.connect("conv:1", b)
        assert a.accepted and b.accepted
        assert manager.topic_count == 1

        # WHEN a message is published to the topic
        await manager.publish("conv:1", {"status": "running"})

        # THEN both sockets receive it
        assert a.sent == [{"status": "running"}]
        assert b.sent == [{"status": "running"}]

    async def test_publish__unknown_topic__is_noop(self) -> None:
        # GIVEN a manager with no subscribers
        manager = self._manager()

        # WHEN publishing to a topic nobody listens on
        await manager.publish("nobody-here", {"x": 1})  # must not raise

        # THEN nothing is tracked
        assert manager.topic_count == 0

    async def test_disconnect__prunes_empty_topic(self) -> None:
        # GIVEN a single subscriber
        manager = self._manager()
        ws = FakeWebSocket()
        await manager.connect("conv:2", ws)

        # WHEN it disconnects
        await manager.disconnect("conv:2", ws)

        # THEN the now-empty topic is pruned
        assert manager.topic_count == 0

    async def test_publish__dead_socket__is_pruned(self) -> None:
        # GIVEN one healthy and one failing socket on a topic
        manager = self._manager()
        good, dead = FakeWebSocket(), FakeWebSocket(fail_on_send=True)
        await manager.connect("conv:3", good)
        await manager.connect("conv:3", dead)

        # WHEN a message is published
        await manager.publish("conv:3", {"n": 1})

        # THEN the failing socket is dropped and the topic keeps the survivor
        assert good.sent == [{"n": 1}]
        assert manager.topic_count == 1

        # AND a second publish reaches only the survivor
        await manager.publish("conv:3", {"n": 2})
        assert good.sent == [{"n": 1}, {"n": 2}]


def test_ws_route__accepts_and_prunes_on_disconnect() -> None:
    # GIVEN the app (REST role active → /ws mounted)
    from api.main import app, bootstrap

    manager = bootstrap.websocket_manager
    before = manager.topic_count

    # WHEN a client connects to a topic
    with TestClient(app).websocket_connect("/ws/smoke-topic") as ws:
        # THEN the topic is registered
        assert manager.topic_count == before + 1
        ws.send_text("ping")  # inbound frames are ignored by the server

    # AND leaving the context disconnects, pruning the empty topic
    assert manager.topic_count == before
