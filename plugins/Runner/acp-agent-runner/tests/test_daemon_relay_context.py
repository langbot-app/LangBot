from __future__ import annotations

import asyncio
import contextvars
import json
import types
from unittest.mock import AsyncMock

import pytest
from pkg import daemon_relay

INVOCATION_MARKER: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "invocation_marker", default=None
)


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

    response = json.loads(websocket.send.await_args.args[0])
    assert response["payload"] == {"marker": "active-run"}
    assert INVOCATION_MARKER.get() is None


def test_local_proxy_always_serializes_empty_http_headers():
    proxy = daemon_relay.LocalMCPProxy(types.SimpleNamespace(), "job-1")
    proxy._server = types.SimpleNamespace(server_address=("127.0.0.1", 12345))

    assert proxy.server_config()["headers"] == []
