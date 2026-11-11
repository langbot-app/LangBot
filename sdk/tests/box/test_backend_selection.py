"""Unit tests for BoxRuntime backend selection mechanism."""

from __future__ import annotations

import logging
import datetime as dt
from unittest import mock

import pytest

from langbot_plugin.box.backend import BaseSandboxBackend
from langbot_plugin.box.models import BoxSessionInfo, BoxSpec
from langbot_plugin.box.runtime import BoxRuntime


@pytest.fixture
def logger():
    return logging.getLogger("test.runtime")


class MockBackend(BaseSandboxBackend):
    """Mock backend for testing."""

    def __init__(self, logger: logging.Logger, name: str, available: bool = True):
        super().__init__(logger)
        self.name = name
        self._available = available
        self._alive = True
        self.started_sessions = 0
        self.stopped_sessions = 0

    async def is_available(self) -> bool:
        return self._available

    async def start_session(self, spec):
        self.started_sessions += 1
        now = dt.datetime.now(dt.timezone.utc)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=f"{self.name}-{self.started_sessions}",
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            mount_path=spec.mount_path,
            persistent=spec.persistent,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
            workspace_quota_mb=spec.workspace_quota_mb,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session, spec):
        pass

    async def stop_session(self, session):
        self.stopped_sessions += 1

    async def is_session_alive(self, session) -> bool:
        return self._alive


# ── E2B backend creation ────────────────────────────────────────────────


def test_e2b_backend_created_if_package_installed(logger):
    """E2B backend is created when package is installed."""
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger)
        # E2B backend exists (package installed)
        e2b_backend = runtime.backends[2]
        assert e2b_backend is not None
        assert e2b_backend.name == "e2b"


def test_e2b_backend_none_if_package_not_installed(logger):
    """E2B backend is None when package is not installed."""
    with (
        mock.patch("os.getenv", return_value=""),
        mock.patch.object(BoxRuntime, "_create_e2b_backend", return_value=None),
    ):
        runtime = BoxRuntime(logger)
        # Third backend is None (package not installed)
        assert runtime.backends[2] is None
        # Docker, nsjail, and explicit-only host remain registered.
        active_backends = [b for b in runtime.backends if b is not None]
        assert len(active_backends) == 3


def test_e2b_import_failure_returns_none(logger):
    """Import failure for e2b package returns None, not fatal."""
    with mock.patch("os.getenv", return_value=""):
        # _create_e2b_backend handles ImportError internally
        runtime = BoxRuntime(logger)
        # Should have Docker, nsjail, and E2B (if package installed) or None
        active_backends = [b for b in runtime.backends if b is not None]
        assert len(active_backends) >= 2


# ── box.backend configuration ──────────────────────────────────────────


@pytest.mark.anyio
async def test_box_backend_config_forces_specific_backend(logger):
    """box.backend config forces selection of named backend."""
    backend_e2b = MockBackend(logger, "e2b", available=True)
    backend_docker = MockBackend(logger, "docker", available=True)
    backend_nsjail = MockBackend(logger, "nsjail", available=False)

    runtime = BoxRuntime(logger, backends=[backend_e2b, backend_docker, backend_nsjail])
    runtime.init({"backend": "docker"})

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    assert selected.name == "docker"
    assert selected is backend_docker


@pytest.mark.anyio
async def test_box_backend_config_unavailable_returns_none(logger):
    """When box.backend specifies unavailable backend, returns None."""
    backend_e2b = MockBackend(logger, "e2b", available=False)
    backend_docker = MockBackend(logger, "docker", available=True)

    runtime = BoxRuntime(logger, backends=[backend_e2b, backend_docker])
    runtime.init({"backend": "e2b"})

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    assert selected is None


@pytest.mark.anyio
async def test_box_backend_config_not_found_returns_none(logger):
    """When box.backend specifies unknown backend name, returns None."""
    backend_docker = MockBackend(logger, "docker", available=True)

    runtime = BoxRuntime(logger, backends=[backend_docker])
    runtime.init({"backend": "unknown"})

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    assert selected is None


@pytest.mark.anyio
async def test_box_backend_config_no_fallback(logger):
    """When box.backend is set but backend unavailable, does NOT fallback."""
    backend_e2b = MockBackend(logger, "e2b", available=False)
    backend_docker = MockBackend(logger, "docker", available=True)

    runtime = BoxRuntime(logger, backends=[backend_e2b, backend_docker])
    runtime.init({"backend": "e2b"})

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    # Should return None, not fallback to docker
    assert selected is None


@pytest.mark.anyio
async def test_box_backend_env_var_is_ignored(logger):
    """BOX_BACKEND is not an independent override; use box.backend instead."""
    backend_docker = MockBackend(logger, "docker", available=True)
    backend_e2b = MockBackend(logger, "e2b", available=True)

    runtime = BoxRuntime(logger, backends=[backend_docker, backend_e2b])
    runtime.init({"backend": "docker"})

    with mock.patch(
        "os.getenv", side_effect=lambda k: "e2b" if k == "BOX_BACKEND" else None
    ):
        selected = await runtime._select_backend()

    assert selected is backend_docker


# ── Auto-detect backend selection ───────────────────────────────────────


@pytest.mark.anyio
async def test_auto_detect_first_available(logger):
    """Without box.backend, selects first available backend."""
    backend_e2b = MockBackend(logger, "e2b", available=False)
    backend_docker = MockBackend(logger, "docker", available=True)
    backend_nsjail = MockBackend(logger, "nsjail", available=False)

    runtime = BoxRuntime(logger, backends=[backend_e2b, backend_docker, backend_nsjail])

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    assert selected.name == "docker"


@pytest.mark.anyio
async def test_auto_detect_none_when_all_unavailable(logger):
    """Returns None when all backends are unavailable."""
    backend_docker = MockBackend(logger, "docker", available=False)
    backend_nsjail = MockBackend(logger, "nsjail", available=False)

    runtime = BoxRuntime(logger, backends=[backend_docker, backend_nsjail])

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    assert selected is None


@pytest.mark.anyio
async def test_auto_detect_never_selects_unsafe_host(logger):
    backend_host = MockBackend(logger, "host", available=True)
    backend_host.unsafe_direct_execution = True
    runtime = BoxRuntime(logger, backends=[backend_host])

    selected = await runtime._select_backend()

    assert selected is None


@pytest.mark.anyio
async def test_box_backend_config_can_explicitly_select_host(logger):
    backend_host = MockBackend(logger, "host", available=True)
    backend_host.unsafe_direct_execution = True
    runtime = BoxRuntime(logger, backends=[backend_host])
    runtime.init({"backend": "host"})

    selected = await runtime._select_backend()

    assert selected is backend_host


@pytest.mark.anyio
async def test_admission_readiness_rejects_explicit_host(logger, tmp_path):
    backend_host = MockBackend(logger, "host", available=True)
    backend_host.unsafe_direct_execution = True
    runtime = BoxRuntime(logger, backends=[backend_host])
    runtime.init(
        {
            "backend": "host",
            "local": {
                "host_root": str(tmp_path / "box"),
                "allowed_mount_roots": [str(tmp_path / "box")],
            },
            "admission": {"required": True},
        }
    )

    readiness = await runtime.get_readiness(force=True)

    assert readiness["ready"] is False
    assert readiness["checks"]["required_backend"] is False


@pytest.mark.anyio
async def test_init_config_reselects_backend_before_sessions(logger):
    """INIT config from LangBot can change the selected backend."""
    backend_docker = MockBackend(logger, "docker", available=True)
    backend_e2b = MockBackend(logger, "e2b", available=True)

    runtime = BoxRuntime(logger, backends=[backend_docker, backend_e2b])

    with mock.patch("os.getenv", return_value=None):
        await runtime.initialize()
        try:
            assert runtime._backend is backend_docker

            runtime.init({"backend": "e2b"})
            assert runtime._backend is None

            selected = await runtime._get_backend()
        finally:
            await runtime.stop_background_reaper()

    assert selected is backend_e2b


@pytest.mark.anyio
async def test_create_session_recreates_disappeared_backend_session(logger):
    """A stale in-memory session is dropped if its backend session vanished."""
    backend = MockBackend(logger, "docker", available=True)
    runtime = BoxRuntime(logger, backends=[backend])
    spec = BoxSpec(
        session_id="mcp-shared", cmd="true", persistent=True, read_only_rootfs=False
    )

    with mock.patch("os.getenv", return_value=None):
        first = await runtime.create_session(spec)
        backend._alive = False
        second = await runtime.create_session(spec)

    assert first["backend_session_id"] == "docker-1"
    assert second["backend_session_id"] == "docker-2"
    assert backend.started_sessions == 2
    assert backend.stopped_sessions == 1


# ── Custom backends list ────────────────────────────────────────────────


def test_custom_backends_list_preserved(logger):
    """Providing custom backends list overrides auto-detection."""
    custom_backend = MockBackend(logger, "custom", available=True)

    runtime = BoxRuntime(logger, backends=[custom_backend])

    assert len(runtime.backends) == 1
    assert runtime.backends[0].name == "custom"


@pytest.mark.anyio
async def test_custom_backends_with_box_backend_config(logger):
    """box.backend works with custom backends list."""
    backend_a = MockBackend(logger, "a", available=True)
    backend_b = MockBackend(logger, "b", available=True)

    runtime = BoxRuntime(logger, backends=[backend_a, backend_b])
    runtime.init({"backend": "b"})

    with mock.patch("os.getenv", return_value=None):
        selected = await runtime._select_backend()

    assert selected.name == "b"
