from __future__ import annotations

import hmac
import inspect
import json
from http import HTTPStatus
import websockets
from collections.abc import Awaitable, Mapping
from typing import Callable, Coroutine, Any
import logging

from langbot_plugin.runtime.io.connections import ws as ws_connection
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.controller import Controller
from langbot_plugin.runtime.io.connection import MAX_MESSAGE_BYTES

logger = logging.getLogger(__name__)
protocol_logger = logging.getLogger(f"{__name__}.protocol")
protocol_logger.setLevel(logging.WARNING)


def process_http_request(
    connection,
    request,
    health_snapshot_provider: Callable[[], Mapping[str, Any]] | None = None,
):
    """Serve aggregate JSON health alongside the WebSocket endpoint."""

    if getattr(request, "path", None) == "/healthz":
        try:
            payload: Mapping[str, Any] = (
                health_snapshot_provider()
                if health_snapshot_provider is not None
                else {"live": True}
            )
            body = json.dumps(
                payload,
                separators=(",", ":"),
                sort_keys=True,
            )
        except Exception:
            logger.exception("Failed to build Plugin Runtime health snapshot")
            return connection.respond(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                '{"live":false}\n',
            )
        return connection.respond(HTTPStatus.OK, body + "\n")
    return None


class WebSocketServerController(Controller):
    """The controller for WebSocket server."""

    _new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]]

    def __init__(
        self,
        port: int,
        *,
        host: str = "0.0.0.0",
        expected_headers: dict[str, str] | None = None,
        request_authenticator: (
            Callable[[Mapping[str, str]], bool | Awaitable[bool]] | None
        ) = None,
        health_snapshot_provider: Callable[[], Mapping[str, Any]] | None = None,
    ):
        self.port = port
        self.host = host
        self.expected_headers = dict(expected_headers or {})
        self.request_authenticator = request_authenticator
        self.health_snapshot_provider = health_snapshot_provider

    async def run(
        self,
        new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]],
    ):
        self._new_connection_callback = new_connection_callback

        async def authenticate_request(connection, request):
            health_response = process_http_request(
                connection,
                request,
                self.health_snapshot_provider,
            )
            if health_response is not None:
                return health_response
            for header, expected_value in self.expected_headers.items():
                supplied_value = request.headers.get(header, "")
                if not supplied_value or not hmac.compare_digest(
                    str(expected_value), str(supplied_value)
                ):
                    return connection.respond(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            if self.request_authenticator is not None:
                authenticated = self.request_authenticator(request.headers)
                if inspect.isawaitable(authenticated):
                    authenticated = await authenticated
                if not authenticated:
                    return connection.respond(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            return None

        server = await websockets.serve(
            self.handle_connection,
            self.host,
            self.port,
            max_size=MAX_MESSAGE_BYTES,
            process_request=authenticate_request,
            logger=protocol_logger,
        )
        logger.info(f"WebSocket server started on {self.host}:{self.port}")
        try:
            await server.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    async def handle_connection(self, websocket: websockets.ServerConnection):
        logger.info(f"New connection from {websocket.remote_address}")
        connection = ws_connection.WebSocketConnection(websocket)
        request = getattr(websocket, "request", None)
        if request is not None:
            connection.request_headers = request.headers
        await self._new_connection_callback(connection)
