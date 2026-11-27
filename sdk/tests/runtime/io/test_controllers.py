from __future__ import annotations

import asyncio
import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from langbot_plugin.runtime.io.connections.stdio import StdioConnection
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.controllers.stdio import client as stdio_client
from langbot_plugin.runtime.io.controllers.stdio import server as stdio_server
from langbot_plugin.runtime.io.controllers.ws import client as ws_client
from langbot_plugin.runtime.io.controllers.ws import server as ws_server


class FakeProcess:
    def __init__(self, stdin=object(), stdout=object()):
        self.stdin = stdin
        self.stdout = stdout
        self.returncode: int | None = 0


class FakeWebSocket:
    remote_address = ("127.0.0.1", 12345)


class FakeWebSocketConnectContext:
    def __init__(self, websocket):
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeServer:
    def __init__(self):
        self.waited = False
        self.closed = False

    async def wait_closed(self):
        self.waited = True

    def close(self):
        self.closed = True


async def test_stdio_client_controller_creates_process_connection(monkeypatch):
    process = FakeProcess()
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return process

    async def callback(connection):
        captured["connection"] = connection

    monkeypatch.setattr(
        stdio_client.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    controller = stdio_client.StdioClientController(
        command="python",
        args=["plugin.py"],
        env={"TOKEN": "secret"},
        working_dir="/tmp/plugin",
    )

    await controller.run(callback)

    assert captured["args"][:2] == ("python", "plugin.py")
    assert captured["kwargs"]["env"] == {"TOKEN": "secret"}
    assert captured["kwargs"]["cwd"] == "/tmp/plugin"
    assert captured["kwargs"]["stderr"] is None
    assert isinstance(captured["connection"], StdioConnection)
    assert captured["connection"].process is process


async def test_stdio_client_controller_captures_stderr_only_when_requested(
    monkeypatch,
):
    process = FakeProcess()
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured.update(kwargs)
        return process

    async def callback(connection):
        return None

    monkeypatch.setattr(
        stdio_client.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    controller = stdio_client.StdioClientController(
        "python",
        [],
        {},
        capture_stderr=True,
    )

    await controller.run(callback)

    assert captured["stderr"] is stdio_client.asyncio.subprocess.PIPE


async def test_stdio_client_controller_can_transfer_process_lifetime_ownership(
    monkeypatch,
):
    process = FakeProcess()
    process.returncode = None

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(
        stdio_client.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    controller = stdio_client.StdioClientController(
        "python",
        [],
        {},
        close_process_on_callback_return=False,
    )

    await controller.run(lambda _connection: asyncio.sleep(0))

    assert controller.process is process
    assert controller.connection is not None


async def test_stdio_client_controller_rejects_missing_pipes(monkeypatch):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess(stdin=None, stdout=object())

    monkeypatch.setattr(
        stdio_client.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    controller = stdio_client.StdioClientController("python", [], {}, ".")

    with pytest.raises(RuntimeError, match="Failed to create subprocess pipes"):
        await controller.run(lambda connection: None)


@pytest.mark.parametrize(
    (
        "exit_stage",
        "expected_result",
        "expected_terminate_calls",
        "expected_kill_calls",
    ),
    [
        ("graceful", True, 0, 0),
        ("terminate", True, 1, 0),
        ("kill", True, 1, 1),
        ("never", False, 1, 1),
    ],
)
async def test_stdio_client_process_stop_uses_bounded_signal_escalation(
    monkeypatch,
    exit_stage,
    expected_result,
    expected_terminate_calls,
    expected_kill_calls,
):
    monkeypatch.setattr(
        stdio_client,
        "_PROCESS_GRACEFUL_EXIT_TIMEOUT_SEC",
        0.001,
    )
    monkeypatch.setattr(
        stdio_client,
        "_PROCESS_TERMINATE_EXIT_TIMEOUT_SEC",
        0.001,
    )
    monkeypatch.setattr(
        stdio_client,
        "_PROCESS_KILL_EXIT_TIMEOUT_SEC",
        0.001,
    )

    class ControlledProcess:
        def __init__(self):
            self.returncode = None
            self.terminate_calls = 0
            self.kill_calls = 0
            self.wait_calls = 0

        def terminate(self):
            self.terminate_calls += 1

        def kill(self):
            self.kill_calls += 1

        async def wait(self):
            self.wait_calls += 1
            if (
                exit_stage == "graceful"
                or exit_stage == "terminate"
                and self.terminate_calls
                or exit_stage == "kill"
                and self.kill_calls
            ):
                self.returncode = (
                    0
                    if exit_stage == "graceful"
                    else -15
                    if exit_stage == "terminate"
                    else -9
                )
                return self.returncode
            await asyncio.Event().wait()

    process = ControlledProcess()

    assert await stdio_client.stop_process(process) is expected_result
    assert process.terminate_calls == expected_terminate_calls
    assert process.kill_calls == expected_kill_calls
    assert process.wait_calls == 1 + expected_terminate_calls + expected_kill_calls


async def test_stdio_server_controller_wraps_standard_streams(monkeypatch):
    captured = {}

    async def fake_connect_stdin_stdout():
        return object(), object()

    async def callback(connection):
        captured["connection"] = connection

    monkeypatch.setattr(
        stdio_server,
        "connect_stdin_stdout",
        fake_connect_stdin_stdout,
    )

    await stdio_server.StdioServerController().run(callback)

    assert isinstance(captured["connection"], StdioConnection)


async def test_websocket_client_controller_invokes_connection_callback(monkeypatch):
    captured = {}
    websocket = FakeWebSocket()

    def fake_connect(
        url,
        open_timeout,
        proxy="__unset__",
        additional_headers=None,
        max_size=None,
    ):
        captured["url"] = url
        captured["open_timeout"] = open_timeout
        captured["proxy"] = proxy
        captured["additional_headers"] = additional_headers
        captured["max_size"] = max_size
        return FakeWebSocketConnectContext(websocket)

    async def callback(connection):
        captured["connection"] = connection

    async def on_failed(controller, exc):
        captured["failure"] = (controller, exc)

    monkeypatch.setattr(ws_client.websockets, "connect", fake_connect)
    controller = ws_client.WebSocketClientController("ws://localhost:9000", on_failed)

    await controller.run(callback)

    assert captured["url"] == "ws://localhost:9000"
    assert captured["open_timeout"] == 10
    # Internal control-plane connections must bypass proxy auto-detection.
    assert captured["proxy"] is None
    assert captured["additional_headers"] is None
    assert captured["max_size"] == ws_client.MAX_MESSAGE_BYTES
    assert isinstance(captured["connection"], WebSocketConnection)
    assert "failure" not in captured


async def test_websocket_client_controller_reports_connection_failure(monkeypatch):
    captured = {}
    error = OSError("network down")

    def fake_connect(
        url,
        open_timeout,
        proxy=None,
        additional_headers=None,
        max_size=None,
    ):
        raise error

    async def callback(connection):
        captured["connection"] = connection

    async def on_failed(controller, exc):
        captured["failure"] = (controller, exc)

    monkeypatch.setattr(ws_client.websockets, "connect", fake_connect)
    controller = ws_client.WebSocketClientController("ws://localhost:9000", on_failed)

    await controller.run(callback)

    assert captured["failure"] == (controller, error)
    assert "connection" not in captured


async def test_websocket_client_controller_sends_additional_headers(monkeypatch):
    captured = {}
    websocket = FakeWebSocket()

    def fake_connect(
        url,
        open_timeout,
        proxy=None,
        additional_headers=None,
        max_size=None,
    ):
        captured["additional_headers"] = additional_headers
        captured["max_size"] = max_size
        return FakeWebSocketConnectContext(websocket)

    async def callback(connection):
        captured["connection"] = connection

    async def on_failed(controller, exc):
        captured["failure"] = (controller, exc)

    monkeypatch.setattr(ws_client.websockets, "connect", fake_connect)
    controller = ws_client.WebSocketClientController(
        "ws://localhost:9000",
        on_failed,
        additional_headers={"X-Control-Token": "secret"},
    )

    await controller.run(callback)

    assert captured["additional_headers"] == {"X-Control-Token": "secret"}
    assert captured["max_size"] == ws_client.MAX_MESSAGE_BYTES
    assert isinstance(captured["connection"], WebSocketConnection)


async def test_websocket_client_controller_passes_additional_headers(monkeypatch):
    captured = {}
    websocket = FakeWebSocket()

    def fake_connect(url, **kwargs):
        captured.update(kwargs)
        return FakeWebSocketConnectContext(websocket)

    async def callback(connection):
        captured["connection"] = connection

    async def on_failed(controller, exc):
        captured["failure"] = (controller, exc)

    monkeypatch.setattr(ws_client.websockets, "connect", fake_connect)
    controller = ws_client.WebSocketClientController(
        "ws://localhost:9000",
        on_failed,
        additional_headers={"X-Control-Token": "secret"},
    )

    await controller.run(callback)

    assert captured["additional_headers"] == {"X-Control-Token": "secret"}
    assert "failure" not in captured


async def test_websocket_server_controller_run_waits_for_server(monkeypatch):
    fake_server = FakeServer()
    captured = {}

    async def fake_serve(handler, host, port, **kwargs):
        captured["handler"] = handler
        captured["host"] = host
        captured["port"] = port
        captured["kwargs"] = kwargs
        return fake_server

    async def callback(connection):
        captured["connection"] = connection

    monkeypatch.setattr(ws_server.websockets, "serve", fake_serve)
    controller = ws_server.WebSocketServerController(port=9000)

    await controller.run(callback)

    assert captured["handler"] == controller.handle_connection
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000
    assert callable(captured["kwargs"]["process_request"])
    assert fake_server.waited is True
    assert fake_server.closed is True


def test_websocket_server_health_endpoint():
    connection = MagicMock()
    response = object()
    connection.respond.return_value = response

    result = ws_server.process_http_request(
        connection, SimpleNamespace(path="/healthz")
    )

    assert result is response
    connection.respond.assert_called_once_with(
        HTTPStatus.OK,
        '{"live":true}\n',
    )


def test_websocket_server_health_endpoint_exposes_aggregate_snapshot():
    connection = MagicMock()
    response = object()
    connection.respond.return_value = response

    result = ws_server.process_http_request(
        connection,
        SimpleNamespace(path="/healthz"),
        lambda: {
            "live": True,
            "resources": {
                "event_loop": {"recent_max_lag_ms": 12.5},
                "plugin_handlers": 3,
            },
        },
    )

    assert result is response
    status, body = connection.respond.call_args.args
    assert status is HTTPStatus.OK
    assert json.loads(body) == {
        "live": True,
        "resources": {
            "event_loop": {"recent_max_lag_ms": 12.5},
            "plugin_handlers": 3,
        },
    }


def test_websocket_server_non_health_request_continues_handshake():
    connection = MagicMock()

    result = ws_server.process_http_request(
        connection, SimpleNamespace(path="/control/ws")
    )

    assert result is None
    connection.respond.assert_not_called()


async def test_websocket_server_controller_rejects_invalid_handshake_header(
    monkeypatch,
):
    fake_server = FakeServer()
    captured = {}

    async def fake_serve(handler, host, port, **kwargs):
        captured.update(kwargs)
        return fake_server

    class HandshakeConnection:
        def respond(self, status, text):
            return status, text

    class Request:
        headers = {"X-Control-Token": "wrong"}

    monkeypatch.setattr(ws_server.websockets, "serve", fake_serve)
    controller = ws_server.WebSocketServerController(
        port=9000,
        expected_headers={"X-Control-Token": "s" * 48},
    )
    await controller.run(lambda connection: None)

    response = await captured["process_request"](HandshakeConnection(), Request())
    assert response[0].value == 401
    assert response[1] == "Unauthorized"


async def test_websocket_server_controller_accepts_valid_handshake_header(monkeypatch):
    fake_server = FakeServer()
    captured = {}

    async def fake_serve(handler, host, port, **kwargs):
        captured.update(kwargs)
        return fake_server

    class Request:
        headers = {"X-Control-Token": "s" * 48}

    monkeypatch.setattr(ws_server.websockets, "serve", fake_serve)
    controller = ws_server.WebSocketServerController(
        port=9000,
        expected_headers={"X-Control-Token": "s" * 48},
    )
    await controller.run(lambda connection: None)

    assert await captured["process_request"](object(), Request()) is None


async def test_websocket_server_controller_uses_dynamic_request_authenticator(
    monkeypatch,
):
    fake_server = FakeServer()
    captured = {}

    async def fake_serve(handler, host, port, **kwargs):
        captured.update(kwargs)
        return fake_server

    class HandshakeConnection:
        def respond(self, status, text):
            return status, text

    class ValidRequest:
        headers = {"X-Registration": "pending"}

    class InvalidRequest:
        headers = {"X-Registration": "replayed"}

    monkeypatch.setattr(ws_server.websockets, "serve", fake_serve)
    controller = ws_server.WebSocketServerController(
        port=9000,
        request_authenticator=lambda headers: (
            headers.get("X-Registration") == "pending"
        ),
    )
    await controller.run(lambda connection: None)

    assert await captured["process_request"](object(), ValidRequest()) is None
    response = await captured["process_request"](
        HandshakeConnection(), InvalidRequest()
    )
    assert response[0].value == 401
    assert response[1] == "Unauthorized"


async def test_websocket_server_controller_wraps_new_connections():
    captured = {}
    controller = ws_server.WebSocketServerController(port=9000)

    async def callback(connection):
        captured["connection"] = connection

    controller._new_connection_callback = callback

    await controller.handle_connection(FakeWebSocket())

    assert isinstance(captured["connection"], WebSocketConnection)
