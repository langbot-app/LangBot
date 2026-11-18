from __future__ import annotations

from typing import Callable, Coroutine, Any

import websockets

from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.connections import ws as ws_connection
from langbot_plugin.runtime.io.controller import Controller
from langbot_plugin.runtime.io.connection import MAX_MESSAGE_BYTES


class WebSocketClientController(Controller):
    """The controller for WebSocket client."""

    def __init__(
        self,
        ws_url: str,
        make_connection_failed_callback: Callable[
            [Controller, Exception | None], Coroutine[Any, Any, None]
        ],
        additional_headers: dict[str, str] | None = None,
    ):
        self.ws_url = ws_url
        self.make_connection_failed_callback = make_connection_failed_callback
        self.additional_headers = dict(additional_headers or {})

    async def run(
        self,
        new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]],
    ):
        try:
            # ``proxy=None`` disables proxy auto-detection. These WebSocket
            # connections are always to internal control-plane endpoints
            # (the plugin runtime / Box runtime, reached over localhost or a
            # Docker-internal service name). Without this, websockets>=14
            # honours HTTP(S)_PROXY env vars and routes the handshake through
            # an external proxy — which cannot reach the internal host and
            # fails with "did not receive a valid HTTP response". This breaks
            # Docker deployments on hosts that inject a proxy into containers
            # (e.g. Docker Desktop with a configured proxy).
            async with websockets.connect(
                self.ws_url,
                open_timeout=10,
                proxy=None,
                max_size=MAX_MESSAGE_BYTES,
                additional_headers=self.additional_headers or None,
            ) as websocket:
                connection = ws_connection.WebSocketConnection(websocket)
                await new_connection_callback(connection)
        except Exception as e:
            await self.make_connection_failed_callback(self, e)
