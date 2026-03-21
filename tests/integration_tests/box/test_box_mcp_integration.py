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

from langbot.pkg.box.client import RemoteBoxRuntimeClient
from langbot.pkg.box.errors import BoxSessionNotFoundError
from langbot.pkg.box.models import BoxManagedProcessSpec, BoxManagedProcessStatus, BoxSpec
from langbot.pkg.box.runtime import BoxRuntime
from langbot.pkg.box.server import create_app as create_server_app

_logger = logging.getLogger('test.box.mcp_integration')

_TEST_IMAGE = 'alpine:latest'


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


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
async def box_server():
    """Yield a (TestServer, RemoteBoxRuntimeClient) backed by a real BoxRuntime."""
    runtime = BoxRuntime(logger=_logger)
    app = create_server_app(runtime)
    server = TestServer(app)
    await server.start_server()
    client = RemoteBoxRuntimeClient(
        base_url=str(server.make_url('')),
        logger=_logger,
    )
    yield server, client
    await client.shutdown()
    await server.close()


# ── 1. Managed process lifecycle ─────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_managed_process_start_and_query(box_server):
    """Start a managed process and query its status."""
    server, client = box_server

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

    # Cleanup
    await client.delete_session('mcp-int-lifecycle')


# ── 2. WebSocket stdio attach ────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_ws_stdio_attach_echo(box_server):
    """Attach to a managed process via WebSocket and verify bidirectional IO."""
    server, client = box_server

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

    # Connect via WebSocket
    ws_url = client.get_managed_process_websocket_url('mcp-int-ws')
    session = aiohttp.ClientSession()
    try:
        async with session.ws_connect(ws_url) as ws:
            # Send a line
            await ws.send_str('hello from test')

            # Expect to receive it back (cat echoes)
            msg = await asyncio.wait_for(ws.receive(), timeout=5)
            assert msg.type == aiohttp.WSMsgType.TEXT
            assert 'hello from test' in msg.data
    finally:
        await session.close()

    await client.delete_session('mcp-int-ws')


# ── 3. Session cleanup removes container ─────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_delete_session_cleans_up(box_server):
    """After deleting a session, it should no longer exist."""
    server, client = box_server

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


# ── 4. GET /v1/sessions/{id} ────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_get_session_returns_details(box_server):
    """GET single session returns session details and managed process info."""
    server, client = box_server

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
    server, client = box_server

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
    server, client = box_server

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
