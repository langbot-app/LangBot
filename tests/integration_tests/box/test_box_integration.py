"""Integration tests for LangBot Box.

These tests verify the end-to-end behavior of the Box sandbox execution
system.  Tests decorated with ``requires_container`` need a real container
runtime (Podman or Docker) and are skipped otherwise.

CI only runs ``tests/unit_tests/``, so these tests never execute in the
CI pipeline.  Run them locally with::

    pytest tests/integration_tests/ -v
"""

from __future__ import annotations

import logging
import shutil
import socket
import subprocess
from types import SimpleNamespace

import pytest
from aiohttp.test_utils import TestServer

from langbot.pkg.box.backend import BaseSandboxBackend
from langbot.pkg.box.client import RemoteBoxRuntimeClient
from langbot.pkg.box.errors import BoxBackendUnavailableError, BoxRuntimeUnavailableError
from langbot.pkg.box.models import BoxExecutionStatus, BoxNetworkMode, BoxSpec
from langbot.pkg.box.runtime import BoxRuntime
from langbot.pkg.box.server import create_app as create_server_app
from langbot.pkg.box.service import BoxService

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

_logger = logging.getLogger('test.box.integration')

# Default image for integration tests — small and fast to pull.
_TEST_IMAGE = 'alpine:latest'


# ── Skip helpers ──────────────────────────────────────────────────────


def _has_container_runtime() -> bool:
    for cmd in ('podman', 'docker'):
        if shutil.which(cmd) is None:
            continue
        try:
            result = subprocess.run(
                [cmd, 'info'],
                capture_output=True,
                timeout=10,
            )
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
async def box_client():
    """Yield a RemoteBoxRuntimeClient backed by a real BoxRuntime HTTP server."""
    runtime = BoxRuntime(logger=_logger)
    app = create_server_app(runtime)
    server = TestServer(app)
    await server.start_server()
    client = RemoteBoxRuntimeClient(
        base_url=str(server.make_url('')),
        logger=_logger,
    )
    yield client
    await client.shutdown()
    await server.close()


# ── 1. Simple command execution ───────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_exec_simple_command(box_client: RemoteBoxRuntimeClient):
    """Box starts a simple command and returns stdout."""
    spec = BoxSpec(
        cmd='echo hello-box',
        session_id='int-simple',
        workdir='/tmp',
        image=_TEST_IMAGE,
    )
    result = await box_client.execute(spec)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert 'hello-box' in result.stdout


# ── 2. Session file persistence ───────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_session_persists_files(box_client: RemoteBoxRuntimeClient):
    """Write a file in one exec, read it back in a second exec on the same session."""
    sid = 'int-persist'

    write_result = await box_client.execute(BoxSpec(
        cmd='echo "hello from file" > /tmp/testfile.txt',
        session_id=sid,
        workdir='/tmp',
        image=_TEST_IMAGE,
    ))
    assert write_result.exit_code == 0

    read_result = await box_client.execute(BoxSpec(
        cmd='cat /tmp/testfile.txt',
        session_id=sid,
        workdir='/tmp',
        image=_TEST_IMAGE,
    ))
    assert read_result.exit_code == 0
    assert 'hello from file' in read_result.stdout


# ── 3. Timeout handling ───────────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_timeout_kills_command(box_client: RemoteBoxRuntimeClient):
    """A long-running command is killed after timeout_sec."""
    spec = BoxSpec(
        cmd='sleep 120',
        session_id='int-timeout',
        workdir='/tmp',
        timeout_sec=3,
        image=_TEST_IMAGE,
    )
    result = await box_client.execute(spec)

    assert result.status == BoxExecutionStatus.TIMED_OUT
    assert result.exit_code is None


# ── 4. Network isolation ─────────────────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_offline_cannot_reach_network(box_client: RemoteBoxRuntimeClient):
    """With network=OFF the sandbox cannot reach the internet."""
    spec = BoxSpec(
        cmd='wget -q -O /dev/null --timeout=3 http://1.1.1.1 2>&1; exit $?',
        session_id='int-offline',
        workdir='/tmp',
        network=BoxNetworkMode.OFF,
        image=_TEST_IMAGE,
    )
    result = await box_client.execute(spec)

    assert result.exit_code != 0


# ── 5. Backend unavailable ───────────────────────────────────────────


class _UnavailableBackend(BaseSandboxBackend):
    """A backend that always reports itself as unavailable."""

    name = 'unavailable'

    def __init__(self):
        super().__init__(logging.getLogger('test'))

    async def is_available(self) -> bool:
        return False

    async def start_session(self, spec):
        raise NotImplementedError

    async def exec(self, session, spec):
        raise NotImplementedError

    async def stop_session(self, session):
        pass


@requires_socket
@pytest.mark.asyncio
async def test_backend_unavailable_returns_error():
    """When no backend is available the full HTTP path returns BoxBackendUnavailableError."""
    runtime = BoxRuntime(logger=_logger, backends=[_UnavailableBackend()])
    app = create_server_app(runtime)
    server = TestServer(app)
    await server.start_server()
    try:
        client = RemoteBoxRuntimeClient(
            base_url=str(server.make_url('')),
            logger=_logger,
        )
        spec = BoxSpec(
            cmd='echo hello',
            session_id='int-no-backend',
            workdir='/tmp',
        )
        with pytest.raises(BoxBackendUnavailableError):
            await client.execute(spec)
        await client.shutdown()
    finally:
        await server.close()


# ── 6. Runtime unreachable ────────────────────────────────────────────


@requires_socket
@pytest.mark.asyncio
async def test_runtime_unreachable_returns_error():
    """Connecting to a non-existent runtime raises BoxRuntimeUnavailableError."""
    client = RemoteBoxRuntimeClient(
        base_url='http://127.0.0.1:19999',
        logger=_logger,
    )
    try:
        with pytest.raises(BoxRuntimeUnavailableError):
            await client.initialize()
    finally:
        await client.shutdown()


# ── 7. Full service-to-runtime path ──────────────────────────────────


@requires_container
@requires_socket
@pytest.mark.asyncio
async def test_full_service_to_remote_runtime(tmp_path):
    """BoxService -> RemoteBoxRuntimeClient -> HTTP -> BoxRuntime -> real backend."""
    runtime = BoxRuntime(logger=_logger)
    app = create_server_app(runtime)
    server = TestServer(app)
    await server.start_server()
    try:
        client = RemoteBoxRuntimeClient(
            base_url=str(server.make_url('')),
            logger=_logger,
        )
        host_dir = tmp_path / 'workspace'
        host_dir.mkdir()

        mock_ap = SimpleNamespace(
            logger=_logger,
            instance_config=SimpleNamespace(
                data={
                    'box': {
                        'profile': 'default',
                        'allowed_host_mount_roots': [str(tmp_path)],
                        'default_host_workspace': str(host_dir),
                    }
                }
            ),
        )

        service = BoxService(mock_ap, client=client)
        await service.initialize()

        query = pipeline_query.Query.model_construct(query_id=42)
        result = await service.execute_sandbox_tool(
            {'cmd': 'echo service-path', 'image': _TEST_IMAGE},
            query,
        )

        assert result['ok'] is True
        assert result['status'] == 'completed'
        assert 'service-path' in result['stdout']
        assert result['session_id'] == '42'
        await client.shutdown()
    finally:
        await server.close()
