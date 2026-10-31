"""Integration tests for Box MCP-related features.

These tests verify managed process lifecycle, WebSocket stdio attach,
session cleanup, and the single-session query API using a real container
runtime.

CI only runs ``tests/unit_tests/``, so these tests never execute in the
CI pipeline.  Run them locally with::

    pytest tests/integration_tests/box/test_box_mcp_integration.py -v
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import socket
import subprocess

import aiohttp
import pytest
from aiohttp.test_utils import TestServer

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import (
    BoxError,
    BoxManagedProcessNotFoundError,
    BoxSessionNotFoundError,
)
from langbot_plugin.box.models import BoxManagedProcessSpec, BoxManagedProcessStatus, BoxSpec
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.security import (
    BOX_CONTROL_TOKEN_HEADER,
    BOX_INSTANCE_HEADER,
    BOX_PLACEMENT_GENERATION_HEADER,
    BOX_WORKSPACE_HEADER,
)
from langbot_plugin.box.server import (
    BoxGenerationFence,
    BoxServerHandler,
    create_ws_relay_app,
)
from langbot_plugin.entities.io.context import ActionContext

_logger = logging.getLogger('test.box.mcp_integration')

_TEST_IMAGE = 'alpine:latest'
_ACTION_CONTEXT = ActionContext(
    instance_uuid='box-integration-instance',
    workspace_uuid='box-integration-workspace',
    placement_generation=1,
)
_CONTROL_TOKEN = 'box-integration-control-token-longer-than-32-bytes'
_RELAY_HEADERS = {
    BOX_CONTROL_TOKEN_HEADER: _CONTROL_TOKEN,
    BOX_INSTANCE_HEADER: _ACTION_CONTEXT.instance_uuid,
    BOX_WORKSPACE_HEADER: _ACTION_CONTEXT.workspace_uuid,
    BOX_PLACEMENT_GENERATION_HEADER: str(_ACTION_CONTEXT.placement_generation),
}


# ── Skip helpers ──────────────────────────────────────────────────────


def _has_container_runtime() -> bool:
    for cmd in ('podman', 'docker'):
        if shutil.which(cmd) is None:
            continue
        try:
            result = subprocess.run([cmd, 'info'], capture_output=True, timeout=10)
            if result.returncode == 0:
                return True
        except Exception:
            continue
    return False


def _can_open_test_socket() -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return False
    sock.close()
    return True


requires_container = pytest.mark.skipif(
    not _has_container_runtime(),
    reason='no container runtime (podman/docker) available',
)

requires_socket = pytest.mark.skipif(
    not _can_open_test_socket(),
    reason='local test environment does not permit opening TCP sockets',
)


# ── Helpers ──────────────────────────────────────────────────────────


class _QueueConnection:
    """In-process Connection backed by asyncio Queues — no real IO."""

    def __init__(self, rx: asyncio.Queue[str], tx: asyncio.Queue[str]):
        self._rx = rx
        self._tx = tx

    async def send(self, message: str) -> None:
        await self._tx.put(message)

    async def receive(self) -> str:
        return await self._rx.get()

    async def close(self) -> None:
        pass


class _TenantBoxClient(ActionRPCBoxClient):
    async def _call(
        self,
        action,
        data,
        timeout=15.0,
        action_context=None,
    ):
        return await super()._call(
            action,
            data,
            timeout=timeout,
            action_context=action_context or _ACTION_CONTEXT,
        )


async def _make_rpc_pair(
    runtime: BoxRuntime,
    generation_fence: BoxGenerationFence,
):
    """Create an in-process RPC pair connected via queues."""
    from langbot_plugin.runtime.io.handler import Handler

    c2s: asyncio.Queue[str] = asyncio.Queue()
    s2c: asyncio.Queue[str] = asyncio.Queue()
    client_conn = _QueueConnection(rx=s2c, tx=c2s)
    server_conn = _QueueConnection(rx=c2s, tx=s2c)

    server_handler = BoxServerHandler(
        server_conn,
        runtime,
        host_control_authenticated=True,
        trusted_instance_uuid=_ACTION_CONTEXT.instance_uuid,
        generation_fence=generation_fence,
    )
    server_task = asyncio.create_task(server_handler.run())

    client_handler = Handler.__new__(Handler)
    Handler.__init__(client_handler, client_conn)
    client_task = asyncio.create_task(client_handler.run())

    client = _TenantBoxClient(logger=_logger)
    client.set_handler(client_handler)

    return client, server_task, client_task


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
async def box_server():
    """Yield a (ws_relay_url, ActionRPCBoxClient) backed by a real BoxRuntime."""
    runtime = BoxRuntime(logger=_logger)
    await runtime.initialize()
    generation_fence = BoxGenerationFence()

    # Start ws relay for managed process attach
    ws_app = create_ws_relay_app(
        runtime,
        control_token=_CONTROL_TOKEN,
        trusted_instance_uuid=_ACTION_CONTEXT.instance_uuid,
        generation_fence=generation_fence,
    )
    ws_server = TestServer(ws_app)
    await ws_server.start_server()

    client, server_task, client_task = await _make_rpc_pair(
        runtime,
        generation_fence,
    )

    ws_relay_url = str(ws_server.make_url(''))
    yield ws_relay_url, client

    server_task.cancel()
    client_task.cancel()
    await runtime.shutdown()
    await ws_server.close()


# ── 1. Managed process lifecycle ─────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_managed_process_start_and_query(box_server):
    """Start a managed process and query its status."""
    ws_relay_url, client = box_server

    # Create session
    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-lifecycle',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)

    # Start a managed process that stays alive
    proc_spec = BoxManagedProcessSpec(
        command='sh',
        args=['-c', 'while true; do sleep 1; done'],
        cwd='/tmp',
    )
    info = await client.start_managed_process('mcp-int-lifecycle', proc_spec)
    assert info.status == BoxManagedProcessStatus.RUNNING

    # Query it
    info2 = await client.get_managed_process('mcp-int-lifecycle')
    assert info2.status == BoxManagedProcessStatus.RUNNING
    assert info2.command == 'sh'

    # Stop only the managed process while keeping the session available
    await client.stop_managed_process('mcp-int-lifecycle')
    with pytest.raises(BoxManagedProcessNotFoundError):
        await client.get_managed_process('mcp-int-lifecycle')
    session_info = await client.get_session('mcp-int-lifecycle')
    assert session_info['session_id'] == 'mcp-int-lifecycle'

    # Cleanup
    await client.delete_session('mcp-int-lifecycle')


# ── 2. WebSocket stdio attach ────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_ws_stdio_attach_echo(box_server):
    """Attach to a managed process via WebSocket and verify bidirectional IO."""
    ws_relay_url, client = box_server

    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-ws',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)

    # Start a cat process (echoes stdin to stdout)
    proc_spec = BoxManagedProcessSpec(
        command='cat',
        args=[],
        cwd='/tmp',
    )
    await client.start_managed_process('mcp-int-ws', proc_spec)

    # Connect via WebSocket (ws relay)
    ws_url = client.get_managed_process_websocket_url(
        'mcp-int-ws',
        ws_relay_url,
        action_context=_ACTION_CONTEXT,
    )
    session = aiohttp.ClientSession()
    try:
        async with session.ws_connect(ws_url, headers=_RELAY_HEADERS) as ws:
            # Send a line
            await ws.send_str('hello from test')

            # Expect to receive it back (cat echoes)
            msg = await asyncio.wait_for(ws.receive(), timeout=5)
            assert msg.type == aiohttp.WSMsgType.TEXT
            assert 'hello from test' in msg.data
    finally:
        await session.close()

    await client.delete_session('mcp-int-ws')


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_ws_stdio_attach_closes_on_generation_advance(box_server):
    """A real attached relay is revoked by the next placement RPC."""

    ws_relay_url, client = box_server
    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-generation',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)
    await client.start_managed_process(
        'mcp-int-generation',
        BoxManagedProcessSpec(command='cat', args=[], cwd='/tmp'),
    )
    ws_url = client.get_managed_process_websocket_url(
        'mcp-int-generation',
        ws_relay_url,
        action_context=_ACTION_CONTEXT,
    )
    second_context = _ACTION_CONTEXT.model_copy(update={'placement_generation': 2})

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, headers=_RELAY_HEADERS) as ws:
            assert await client.get_sessions(action_context=second_context) == []
            close_message = await asyncio.wait_for(ws.receive(), timeout=5)
            assert close_message.type in {
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
            }

    with pytest.raises(BoxError, match='Stale Box placement generation'):
        await client.get_sessions(action_context=_ACTION_CONTEXT)


# ── 3. Session cleanup removes container ─────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_delete_session_cleans_up(box_server):
    """After deleting a session, it should no longer exist."""
    ws_relay_url, client = box_server

    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-cleanup',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)

    # Start a process
    proc_spec = BoxManagedProcessSpec(
        command='sleep',
        args=['3600'],
        cwd='/tmp',
    )
    await client.start_managed_process('mcp-int-cleanup', proc_spec)

    # Delete
    await client.delete_session('mcp-int-cleanup')

    # Session should be gone
    with pytest.raises(BoxSessionNotFoundError):
        await client.get_session('mcp-int-cleanup')


# ── 4. GET session details ────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_get_session_returns_details(box_server):
    """Get single session returns session details and managed process info."""
    ws_relay_url, client = box_server

    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-get',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)

    # Query without managed process
    info = await client.get_session('mcp-int-get')
    assert info['session_id'] == 'mcp-int-get'
    assert info['image'] == _TEST_IMAGE
    assert 'managed_process' not in info

    # Start a process and query again
    proc_spec = BoxManagedProcessSpec(
        command='sleep',
        args=['3600'],
        cwd='/tmp',
    )
    await client.start_managed_process('mcp-int-get', proc_spec)

    info2 = await client.get_session('mcp-int-get')
    assert info2['session_id'] == 'mcp-int-get'
    assert 'managed_process' in info2
    assert info2['managed_process']['status'] == BoxManagedProcessStatus.RUNNING.value

    await client.delete_session('mcp-int-get')


# ── 5. Process exit detected ────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_process_exit_detected(box_server):
    """When a managed process exits, its status should reflect EXITED."""
    ws_relay_url, client = box_server

    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-exit',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)

    # Start a process that exits immediately
    proc_spec = BoxManagedProcessSpec(
        command='sh',
        args=['-c', 'echo done && exit 0'],
        cwd='/tmp',
    )
    await client.start_managed_process('mcp-int-exit', proc_spec)

    # Wait a bit for process to exit
    await asyncio.sleep(2)

    info = await client.get_managed_process('mcp-int-exit')
    assert info.status == BoxManagedProcessStatus.EXITED
    assert info.exit_code == 0

    await client.delete_session('mcp-int-exit')


# ── 6. Instance ID orphan cleanup ───────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_orphan_cleanup_preserves_own_containers(box_server):
    """Orphan cleanup should not remove containers belonging to the current instance."""
    ws_relay_url, client = box_server

    # Create a session (container gets current instance ID label)
    spec = BoxSpec(
        cmd='',
        session_id='mcp-int-orphan',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    await client.create_session(spec)

    # Verify session exists
    sessions = await client.get_sessions()
    assert any(s['session_id'] == 'mcp-int-orphan' for s in sessions)

    # Trigger status check (which doesn't clean up own containers)
    status = await client.get_status()
    assert status['active_sessions'] >= 1

    # Our session should still exist
    sessions = await client.get_sessions()
    assert any(s['session_id'] == 'mcp-int-orphan' for s in sessions)

    await client.delete_session('mcp-int-orphan')
