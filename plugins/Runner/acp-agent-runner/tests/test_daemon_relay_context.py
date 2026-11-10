from __future__ import annotations

import asyncio
import contextvars
import json
import types
from unittest.mock import AsyncMock

import pytest
from pkg import daemon_relay

INVOCATION_MARKER: contextvars.ContextVar[str | None] = contextvars.ContextVar("invocation_marker", default=None)


@pytest.mark.asyncio
async def test_daemon_listener_is_created_in_tenant_free_context(monkeypatch):
    observed = []
    expected_server = object()

    async def fake_serve(_handler, _host, _port):
        observed.append(INVOCATION_MARKER.get())
        return expected_server

    monkeypatch.setattr(daemon_relay.websockets, "serve", fake_serve)
    token = INVOCATION_MARKER.set("first-run")
    try:
        server = await daemon_relay._create_tenant_free_daemon_server(object(), "127.0.0.1", 0)
    finally:
        INVOCATION_MARKER.reset(token)

    assert server is expected_server
    assert observed == [None]


@pytest.mark.asyncio
async def test_mcp_request_uses_captured_run_context(monkeypatch):
    hub = daemon_relay.AgentRuntimeDaemonHub()
    websocket = types.SimpleNamespace(send=AsyncMock())
    connection = {
        "daemon_id": "daemon-1",
        "websocket": websocket,
        "last_seen_at": 0.0,
        "send_lock": asyncio.Lock(),
    }
    hub._connections["daemon-1"] = connection

    token = INVOCATION_MARKER.set("active-run")
    try:
        tool_context = contextvars.copy_context()
    finally:
        INVOCATION_MARKER.reset(token)

    tools = object()
    hub._jobs["job-1"] = {
        "job_id": "job-1",
        "owner": connection,
        "tools": tools,
        "tool_context": tool_context,
    }

    async def fake_handle(received_tools, _payload):
        assert received_tools is tools
        return {"marker": INVOCATION_MARKER.get()}

    monkeypatch.setattr(daemon_relay, "handle_agent_runtime_mcp_payload", fake_handle)
    assert INVOCATION_MARKER.get() is None

    await hub._handle_message(
        connection,
        json.dumps(
            {
                "type": "mcp.request",
                "job_id": "job-1",
                "request_id": "request-1",
                "payload": {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            }
        ),
    )
    await asyncio.gather(*connection["mcp_tasks"])

    response = json.loads(websocket.send.await_args.args[0])
    assert response["payload"] == {"marker": "active-run"}
    assert INVOCATION_MARKER.get() is None


@pytest.mark.asyncio
async def test_slow_mcp_request_does_not_block_connection(monkeypatch):
    hub = daemon_relay.AgentRuntimeDaemonHub()
    websocket = types.SimpleNamespace(send=AsyncMock())
    connection = {
        "daemon_id": "daemon-1",
        "websocket": websocket,
        "last_seen_at": 0.0,
        "send_lock": asyncio.Lock(),
    }
    hub._connections["daemon-1"] = connection
    hub._jobs["job-1"] = {
        "job_id": "job-1",
        "owner": connection,
        "tools": object(),
        "tool_context": contextvars.copy_context(),
    }
    release = asyncio.Event()

    async def slow_handle(_tools, _payload):
        await release.wait()
        return {"ok": True}

    monkeypatch.setattr(daemon_relay, "handle_agent_runtime_mcp_payload", slow_handle)
    request = {"type": "mcp.request", "job_id": "job-1", "request_id": "r1", "payload": {}}
    await asyncio.wait_for(hub._handle_message(connection, json.dumps(request)), 1)
    await asyncio.wait_for(hub._handle_message(connection, json.dumps({"type": "daemon.ping"})), 1)

    assert json.loads(websocket.send.await_args.args[0]) == {"type": "daemon.pong"}
    release.set()
    await asyncio.gather(*connection["mcp_tasks"])
    response = json.loads(websocket.send.await_args.args[0])
    assert response["type"] == "mcp.response"
    assert response["payload"] == {"ok": True}


def test_local_proxy_always_serializes_empty_http_headers():
    proxy = daemon_relay.LocalMCPProxy(types.SimpleNamespace(), "job-1")
    proxy._server = types.SimpleNamespace(server_address=("127.0.0.1", 12345))

    assert proxy.server_config() == {
        "name": proxy.server_name,
        "type": "http",
        "url": "http://127.0.0.1:12345/mcp",
        "headers": [],
    }


def test_mcp_server_to_acp_uses_name_value_arrays():
    from langbot_plugin.api.agent_tools.mcp_config import AgentMCPServerConfig
    from pkg.session import mcp_server_to_acp

    http = AgentMCPServerConfig.http(name="lb", url="http://x/mcp", headers={"Authorization": "Bearer t"})
    assert mcp_server_to_acp(http)["headers"] == [{"name": "Authorization", "value": "Bearer t"}]
    stdio = AgentMCPServerConfig.stdio(name="lb", command="python", args=["-m", "x"], env={"A": "1"})
    assert mcp_server_to_acp(stdio) == {
        "name": "lb",
        "type": "stdio",
        "command": "python",
        "args": ["-m", "x"],
        "env": [{"name": "A", "value": "1"}],
    }


@pytest.mark.asyncio
async def test_disconnect_releases_daemon_id_and_cancels_inflight_mcp(monkeypatch):
    hub = daemon_relay.AgentRuntimeDaemonHub()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def hanging_handle(_tools, _payload):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(daemon_relay, "handle_agent_runtime_mcp_payload", hanging_handle)

    class FakeSocket:
        def __init__(self):
            self.send = AsyncMock()
            self.close = AsyncMock()

        async def recv(self):
            return json.dumps({"type": "daemon.hello", "daemon_id": "daemon-1", "protocol": "coding-relay-v1"})

        def __aiter__(self):
            return self._messages()

        async def _messages(self):
            hub._jobs["job-1"] = {
                "job_id": "job-1",
                "owner": hub._connections["daemon-1"],
                "tools": object(),
                "tool_context": contextvars.copy_context(),
                "done": asyncio.Event(),
            }
            hub._jobs["job-1"]["done"].set()
            yield json.dumps({"type": "mcp.request", "job_id": "job-1", "request_id": "r1", "payload": {}})
            await started.wait()

    await asyncio.wait_for(hub._handle_connection(FakeSocket()), 2)

    assert cancelled.is_set()
    assert "daemon-1" not in hub._connections
    assert "daemon-1" not in hub._fenced
