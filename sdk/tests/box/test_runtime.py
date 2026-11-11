"""Unit tests for the BoxRuntime session manager.

These tests inject a fake backend implementing the ``BaseSandboxBackend``
interface, so they exercise the real ``BoxRuntime`` logic (config handling,
session create/reuse, compatibility checks, expiry/reaping, execute flow,
status, backend selection) without Docker, nsjail, or E2B.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
from unittest import mock

import pytest

from langbot_plugin.box.backend import BaseSandboxBackend, DockerBackend
from langbot_plugin.box.errors import (
    BoxBackendUnavailableError,
    BoxCapacityExceededError,
    BoxError,
    BoxManagedProcessNotFoundError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxReadinessError,
    BoxValidationError,
)
from langbot_plugin.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxManagedProcessSpec,
    BoxManagedProcessStatus,
    BoxMountSpec,
    BoxHostMountMode,
    BoxSessionInfo,
    BoxSpec,
)
from langbot_plugin.box.runtime import BoxRuntime, _compute_extra_mounts_key
from langbot_plugin.entities.io.context import ActionContext

_UTC = dt.timezone.utc


def test_session_mount_signature_includes_content_digest():
    def key(digest: str):
        return _compute_extra_mounts_key(
            BoxSpec(
                session_id="revision-session",
                extra_mounts=[
                    BoxMountSpec(
                        host_path="/tmp/revision",
                        mount_path="/workspace/.skills/demo",
                        mode=BoxHostMountMode.READ_ONLY,
                        content_digest=digest,
                    )
                ],
            )
        )

    assert key("sha256:" + "1" * 64) != key("sha256:" + "2" * 64)


@pytest.mark.anyio
async def test_execution_scoped_mounts_preserve_shared_session(logger):
    backend = FakeBackend(logger)
    backend.execution_scoped_mounts = True
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def controlled_exec(
        session: BoxSessionInfo,
        spec: BoxSpec,
    ) -> BoxExecutionResult:
        backend.exec_calls.append((session.backend_session_id, spec.cmd))
        if spec.cmd == "v1":
            first_started.set()
            await release_first.wait()
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=backend.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout=spec.cmd,
            stderr="",
            duration_ms=1,
        )

    backend.exec = controlled_exec
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])

    def spec(command: str, digit: str) -> BoxSpec:
        return _make_spec(
            "revision-session",
            cmd=command,
            extra_mounts=[
                BoxMountSpec(
                    host_path=f"/tmp/revision-{digit}",
                    mount_path="/workspace/.skills/demo",
                    mode=BoxHostMountMode.READ_ONLY,
                    content_digest="sha256:" + digit * 64,
                )
            ],
        )

    first_task = asyncio.create_task(runtime.execute(spec("v1", "1")))
    await asyncio.wait_for(first_started.wait(), timeout=1)
    queued_task = asyncio.create_task(runtime.execute(spec("queued-v1", "1")))
    await _wait_until(lambda: runtime._active_exec_counts["revision-session"] == 2)
    second_task = asyncio.create_task(runtime.execute(spec("v2", "2")))
    await asyncio.sleep(0.05)

    assert not queued_task.done()
    assert not second_task.done()
    backend.stop_session.assert_not_awaited()

    release_first.set()
    results = await asyncio.wait_for(
        asyncio.gather(first_task, queued_task, second_task, return_exceptions=True),
        timeout=2,
    )

    assert isinstance(results[1], BoxExecutionResult), repr(results[1])
    assert [result.stdout for result in results] == ["v1", "queued-v1", "v2"]
    assert backend.exec_calls == [
        ("fake-1", "v1"),
        ("fake-1", "queued-v1"),
        ("fake-1", "v2"),
    ]
    backend.stop_session.assert_not_awaited()


@pytest.fixture
def logger():
    return logging.getLogger("test.box.runtime")


class FakeBackend(BaseSandboxBackend):
    """Fake backend with AsyncMock-style hooks for BoxRuntime tests.

    Each created session gets a unique ``backend_session_id`` so reuse vs
    recreate can be asserted by inspecting returned info.
    """

    def __init__(
        self,
        logger: logging.Logger,
        name: str = "fake",
        available: bool = True,
    ):
        super().__init__(logger)
        self.name = name
        self._available = available
        self._alive = True
        self.started_sessions = 0
        self.stopped_sessions = 0
        self.exec_calls: list[tuple[str, str]] = []
        # Result returned by exec(); overridable per-test.
        self.exec_status = BoxExecutionStatus.COMPLETED
        self.exec_exit_code: int | None = 0
        self.initialize_calls = 0
        # Wrap call-tracked methods in AsyncMock so tests can assert on them.
        # These shadow the concrete class-level methods defined below (which
        # satisfy the ABC's abstractmethod requirement at class definition).
        self.is_available = mock.AsyncMock(side_effect=self._is_available)
        self.is_session_alive = mock.AsyncMock(side_effect=self._is_session_alive)
        self.stop_session = mock.AsyncMock(side_effect=self._stop_session)

    async def initialize(self):
        self.initialize_calls += 1

    # Concrete class-level implementations of the abstract methods so the
    # class is instantiable. Instances replace these with AsyncMocks (above)
    # that delegate to the matching ``_`` helpers.
    async def is_available(self) -> bool:
        return await self._is_available()

    async def stop_session(self, session: BoxSessionInfo):
        await self._stop_session(session)

    async def _is_available(self) -> bool:
        return self._available

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        self.started_sessions += 1
        now = dt.datetime.now(_UTC)
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

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        self.exec_calls.append((session.backend_session_id, spec.cmd))
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=self.exec_status,
            exit_code=self.exec_exit_code,
            stdout="hello",
            stderr="",
            duration_ms=12,
        )

    async def _stop_session(self, session: BoxSessionInfo):
        self.stopped_sessions += 1

    async def _is_session_alive(self, session: BoxSessionInfo) -> bool:
        return self._alive

    async def start_managed_process(self, session: BoxSessionInfo, spec):
        proc = FakeProcess()
        self.last_process = proc
        return proc


class FakeProcess:
    """Minimal stand-in for asyncio.subprocess.Process.

    ``wait()`` blocks until ``finish()`` is called, so ``is_running`` stays
    True while the managed process is "running" in a test.
    """

    def __init__(self):
        self.returncode: int | None = None
        self._done = asyncio.Event()
        self.stdin = mock.Mock()
        self.stdout = None
        # No stderr stream → the drain task returns immediately.
        self.stderr = None
        self.terminate = mock.Mock(side_effect=self._terminate)
        self.kill = mock.Mock(side_effect=self._kill)

    def _terminate(self):
        # Emulate the process exiting on SIGTERM.
        self.returncode = -15
        self._done.set()

    def _kill(self):
        self.returncode = -9
        self._done.set()

    def finish(self, code: int = 0):
        self.returncode = code
        self._done.set()

    async def wait(self) -> int:
        await self._done.wait()
        return self.returncode if self.returncode is not None else 0


class _ChunkStream:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    async def read(self, _size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def _make_spec(session_id: str = "s1", **kwargs) -> BoxSpec:
    base = {"session_id": session_id, "cmd": "echo hi", "read_only_rootfs": False}
    base.update(kwargs)
    return BoxSpec(**base)


@pytest.mark.anyio
async def test_managed_process_stderr_capture_and_logging_are_bounded():
    logger = mock.Mock(spec=logging.Logger)
    backend = FakeBackend(logger)
    process = FakeProcess()
    process.stderr = _ChunkStream([b"x" * 1000 for _ in range(8)])

    async def start_managed_process(_session, _spec):
        backend.last_process = process
        return process

    backend.start_managed_process = start_managed_process
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])

    await runtime.create_session(_make_spec("stderr"))
    await runtime.start_managed_process(
        "stderr", BoxManagedProcessSpec(command="daemon")
    )
    await _wait_until(
        lambda: any(
            "suppressed managed-process stderr chunks" in str(call)
            for call in logger.warning.call_args_list
        )
    )

    managed = runtime._sessions["stderr"].managed_processes["default"]
    assert managed.stderr_total_len <= 4000
    detailed_logs = [
        call
        for call in logger.info.call_args_list
        if "managed process stderr:" in str(call)
    ]
    assert len(detailed_logs) == 4
    assert any("suppressed=4" in str(call) for call in logger.warning.call_args_list)

    await runtime.stop_managed_process("stderr", "default")


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    async def _poll():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=timeout)


# ── construction / config handling ─────────────────────────────────────


def test_init_without_env_config_has_empty_box_config(logger):
    """No LANGBOT_BOX_CONFIG → empty parsed config."""
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
    assert runtime._box_config == {}
    assert runtime.session_ttl_sec == 300
    assert len(runtime.instance_id) == 12


def test_init_reads_langbot_box_config_env(logger):
    """LANGBOT_BOX_CONFIG env JSON is parsed into _box_config."""
    payload = {"backend": "fake", "fake": {"foo": "bar"}}
    with mock.patch("os.getenv", return_value=json.dumps(payload)):
        runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
    assert runtime._box_config == payload


def test_init_invalid_env_config_is_ignored(logger):
    """Malformed LANGBOT_BOX_CONFIG JSON is swallowed (warning) → empty config."""
    with mock.patch("os.getenv", return_value="{not valid json"):
        runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
    assert runtime._box_config == {}


def test_init_method_applies_config_and_resets_backend(logger):
    """init() merges config, applies to backends, resets backend when idle."""
    backend = FakeBackend(logger, name="fake")
    backend.configure = mock.Mock()
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
    runtime._backend = backend  # pretend already selected

    runtime.init({"backend": "fake", "fake": {"cpus": 2}})

    assert runtime._box_config["backend"] == "fake"
    backend.configure.assert_called_once_with({"cpus": 2})
    # No active sessions → backend reset so it re-selects with new config.
    assert runtime._backend is None


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("max_sessions", 5_001),
        ("max_sessions", True),
        ("max_managed_processes", 1_025),
        ("max_completed_processes", 10_001),
        ("max_admission_records", 250_001),
        ("max_rpc_file_bytes", 100 * 1024 * 1024 + 1),
        ("completed_process_retention_sec", 86_401),
    ],
)
def test_runtime_rejects_limits_above_hard_capacity(logger, name, value):
    payload = {"limits": {name: value}}
    with mock.patch(
        "os.getenv",
        side_effect=lambda key, default="": json.dumps(payload)
        if key == "LANGBOT_BOX_CONFIG"
        else default,
    ):
        with pytest.raises(ValueError, match=rf"box\.limits\.{name}"):
            BoxRuntime(logger, backends=[FakeBackend(logger)])


def test_runtime_config_update_is_atomic_when_limit_is_invalid(logger):
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
    original_config = dict(runtime._box_config)
    original_max_sessions = runtime.max_sessions

    with pytest.raises(ValueError, match=r"box\.limits\.max_sessions"):
        runtime.init(
            {
                "backend": "fake",
                "limits": {"max_sessions": 5_001},
            }
        )

    assert runtime._box_config == original_config
    assert runtime.max_sessions == original_max_sessions


def test_verify_shared_workspace_reads_only_valid_nofollow_marker(logger, tmp_path):
    runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
    root = tmp_path / "box"
    runtime.init(
        {
            "local": {
                "host_root": str(root),
                "default_workspace": "shared",
                "allowed_mount_roots": [str(root)],
            }
        }
    )
    marker_name = ".langbot-box-volume-probe-" + "a" * 32
    marker = root / "shared" / marker_name
    payload = os.urandom(64)
    marker.write_bytes(payload)

    result = runtime.verify_shared_workspace(marker_name)

    assert result == {
        "marker_name": marker_name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    with pytest.raises(ValueError, match="probe basename"):
        runtime.verify_shared_workspace("../shared/secret")


def test_verify_shared_workspace_rejects_missing_and_symlink_markers(logger, tmp_path):
    runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
    root = tmp_path / "box"
    runtime.init(
        {
            "local": {
                "host_root": str(root),
                "default_workspace": "shared",
                "allowed_mount_roots": [str(root)],
            }
        }
    )
    marker_name = ".langbot-box-volume-probe-" + "b" * 32
    with pytest.raises(BoxReadinessError, match="cannot read"):
        runtime.verify_shared_workspace(marker_name)

    secret = tmp_path / "secret"
    secret.write_bytes(b"not the shared marker")
    marker = root / "shared" / marker_name
    try:
        marker.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    with pytest.raises(BoxReadinessError, match="cannot read"):
        runtime.verify_shared_workspace(marker_name)


def test_init_method_applies_docker_cpu_limit_config(logger):
    """box.docker.cpu_limit_enabled is forwarded to the Docker backend."""
    backend = DockerBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])

    runtime.init({"docker": {"cpu_limit_enabled": "false"}})

    assert backend.cpu_limit_enabled is False


def test_init_method_creates_default_workspace_on_box_runtime_host(logger, tmp_path):
    """Default workspace is initialized by the Box runtime, not LangBot."""
    host_root = tmp_path / "box"
    backend = FakeBackend(logger, name="fake")
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])

    runtime.init(
        {
            "backend": "fake",
            "local": {"host_root": str(host_root), "allowed_mount_roots": []},
        }
    )

    assert (host_root / "default").is_dir()


@pytest.mark.anyio
async def test_init_method_keeps_backend_when_sessions_exist(logger):
    """init() must NOT reset backend while sessions are live."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("keep"))
    runtime.init({"backend": "fake"})
    assert runtime._backend is backend


@pytest.mark.anyio
async def test_initialize_applies_config_selects_and_cleans_orphans(logger):
    """initialize() applies env config, selects backend, sets instance_id, cleans orphans."""
    backend = FakeBackend(logger, name="fake")
    backend.configure = mock.Mock()
    backend.cleanup_orphaned_containers = mock.AsyncMock()
    cfg = json.dumps({"backend": "fake", "fake": {"cpus": 1}})
    with mock.patch("os.getenv", return_value=cfg):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.initialize()

    try:
        assert runtime._backend is backend
        backend.configure.assert_called_once_with({"cpus": 1})
        assert backend.instance_id == runtime.instance_id
        backend.cleanup_orphaned_containers.assert_awaited_once_with(
            runtime.instance_id
        )
    finally:
        await runtime.stop_background_reaper()


@pytest.mark.anyio
async def test_initialize_creates_default_workspace_from_env_config(logger, tmp_path):
    host_root = tmp_path / "box"
    backend = FakeBackend(logger, name="fake")
    backend.cleanup_orphaned_containers = mock.AsyncMock()
    cfg = json.dumps(
        {
            "backend": "fake",
            "local": {"host_root": str(host_root), "allowed_mount_roots": []},
        }
    )

    with mock.patch("os.getenv", return_value=cfg):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.initialize()

    try:
        assert (host_root / "default").is_dir()
    finally:
        await runtime.stop_background_reaper()


@pytest.mark.anyio
async def test_initialize_orphan_cleanup_failure_is_swallowed(logger):
    """A failing orphan cleanup must not raise out of initialize()."""
    backend = FakeBackend(logger)
    backend.cleanup_orphaned_containers = mock.AsyncMock(
        side_effect=RuntimeError("boom")
    )
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.initialize()  # should not raise
    try:
        assert runtime._backend is backend
    finally:
        await runtime.stop_background_reaper()


# ── _get_or_create_session: create vs reuse ─────────────────────────────


@pytest.mark.anyio
async def test_create_session_creates_new(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        info = await runtime.create_session(_make_spec("alpha"))

    assert backend.started_sessions == 1
    assert info["session_id"] == "alpha"
    assert info["backend_session_id"] == "fake-1"
    assert len(runtime._sessions) == 1


@pytest.mark.anyio
async def test_create_session_reuses_existing(logger):
    """Same session_id + compatible spec reuses the live session."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        first = await runtime.create_session(_make_spec("beta"))
        second = await runtime.create_session(_make_spec("beta"))

    assert backend.started_sessions == 1  # not started again
    assert first["backend_session_id"] == second["backend_session_id"] == "fake-1"
    backend.is_session_alive.assert_awaited()  # liveness checked on reuse


@pytest.mark.anyio
async def test_reuse_recreates_when_backend_session_dead(logger):
    """If backend reports the session is dead, it is dropped and recreated."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        first = await runtime.create_session(_make_spec("gamma"))
        backend._alive = False
        second = await runtime.create_session(_make_spec("gamma"))

    assert first["backend_session_id"] == "fake-1"
    assert second["backend_session_id"] == "fake-2"
    assert backend.started_sessions == 2
    assert backend.stopped_sessions == 1


# ── _assert_session_compatible across _COMPAT_FIELDS ────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field,changed",
    [
        ("image", "other/image:latest"),
        ("cpus", 2.0),
        ("pids_limit", 64),
        ("workspace_quota_mb", 50),
        ("persistent", True),
    ],
)
async def test_incompatible_reuse_raises_conflict(logger, field, changed):
    """Reusing a session_id with a differing _COMPAT_FIELD raises conflict."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("delta"))
        with pytest.raises(BoxSessionConflictError) as exc_info:
            await runtime.create_session(_make_spec("delta", **{field: changed}))

    assert field in str(exc_info.value)
    # Conflict means we did not start a second backend session.
    assert backend.started_sessions == 1


@pytest.mark.anyio
async def test_compatible_reuse_does_not_raise(logger):
    """Differing-but-non-compat field (e.g. cmd/timeout) still reuses."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("eps", cmd="echo a", timeout_sec=10))
        info = await runtime.create_session(
            _make_spec("eps", cmd="echo b", timeout_sec=99)
        )
    assert info["backend_session_id"] == "fake-1"
    assert backend.started_sessions == 1


# ── execute flow ────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_execute_empty_cmd_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxValidationError):
            await runtime.execute(_make_spec("z", cmd=""))


@pytest.mark.anyio
async def test_execute_creates_session_and_runs(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        result = await runtime.execute(_make_spec("run1", cmd="echo hi"))

    assert isinstance(result, BoxExecutionResult)
    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "hello"
    assert backend.started_sessions == 1
    assert backend.exec_calls == [("fake-1", "echo hi")]
    assert len(runtime._sessions) == 1


@pytest.mark.anyio
async def test_execute_updates_last_used_at(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("run2"))
        before = runtime._sessions["run2"].info.last_used_at
        await runtime.execute(_make_spec("run2", cmd="echo hi"))
        after = runtime._sessions["run2"].info.last_used_at
    assert after >= before


@pytest.mark.anyio
async def test_execute_timeout_drops_session(logger):
    """A TIMED_OUT result triggers the session to be dropped & backend stopped."""
    backend = FakeBackend(logger)
    backend.exec_status = BoxExecutionStatus.TIMED_OUT
    backend.exec_exit_code = None
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        result = await runtime.execute(_make_spec("to", cmd="sleep 999"))

    assert result.status == BoxExecutionStatus.TIMED_OUT
    assert "to" not in runtime._sessions
    backend.stop_session.assert_awaited_once()


# ── session expiry / reaping ────────────────────────────────────────────


@pytest.mark.anyio
async def test_reap_expired_sessions(logger):
    """Sessions idle past TTL are reaped on the next create/exec under lock."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=60)
        await runtime.create_session(_make_spec("old"))
        # Force the session to look stale.
        stale = dt.datetime.now(_UTC) - dt.timedelta(seconds=120)
        runtime._sessions["old"].info.last_used_at = stale

        # Touching another session triggers reaping of expired ones.
        await runtime.create_session(_make_spec("fresh"))
        await _wait_until(lambda: backend.stop_session.await_count == 1)

    assert "old" not in runtime._sessions
    assert "fresh" in runtime._sessions
    backend.stop_session.assert_awaited_once()


@pytest.mark.anyio
async def test_reap_skips_persistent_sessions(logger):
    """Persistent sessions are never reaped even when idle."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=60)
        await runtime.create_session(_make_spec("keep", persistent=True))
        runtime._sessions["keep"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(seconds=999)
        async with runtime._lock:
            await runtime._reap_expired_sessions_locked()

    assert "keep" in runtime._sessions
    backend.stop_session.assert_not_awaited()


@pytest.mark.anyio
async def test_persistent_cloud_sessions_do_not_trigger_global_reaper_scan(
    logger,
):
    """Creating another persistent session must not scan all tenants."""

    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError("Persistent Box sessions were globally scanned")

        def items(self):
            raise AssertionError("Persistent Box sessions were globally scanned")

        def values(self):
            raise AssertionError("Persistent Box sessions were globally scanned")

    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(
            logger,
            backends=[backend],
            session_ttl_sec=60,
        )
        await runtime.create_session(_make_spec("first", persistent=True))
        runtime._sessions = NoGlobalIterationDict(runtime._sessions)

        second = await runtime.create_session(_make_spec("second", persistent=True))
        async with runtime._lock:
            cleanup_tasks = await runtime._reap_expired_sessions_locked()
        status = await runtime.get_status()

    assert second["session_id"] == "second"
    assert cleanup_tasks == []
    assert status["active_sessions"] == 2
    assert status["managed_processes"] == 0
    assert runtime._expirable_session_ids == set()


@pytest.mark.anyio
async def test_reap_disabled_when_ttl_non_positive(logger):
    """ttl <= 0 disables reaping entirely."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=0)
        await runtime.create_session(_make_spec("immortal"))
        runtime._sessions["immortal"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(days=7)
        async with runtime._lock:
            await runtime._reap_expired_sessions_locked()

    assert "immortal" in runtime._sessions
    backend.stop_session.assert_not_awaited()


@pytest.mark.anyio
async def test_background_reaper_drops_idle_session_without_new_request(logger):
    """The background reaper cleans idle sessions without another RPC call."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=0.05)
        await runtime.initialize()

    try:
        await runtime.create_session(_make_spec("idle"))
        runtime._sessions["idle"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(seconds=1)

        await _wait_until(
            lambda: (
                "idle" not in runtime._sessions
                and backend.stop_session.await_count == 1
            )
        )

        backend.stop_session.assert_awaited_once()
    finally:
        await runtime.stop_background_reaper()


@pytest.mark.anyio
async def test_slow_reaper_cleanup_only_blocks_same_session_id(logger):
    """Slow backend cleanup should not hold the global runtime lock."""
    backend = FakeBackend(logger)
    stop_started = asyncio.Event()
    release_stop = asyncio.Event()

    async def slow_stop_session(session: BoxSessionInfo):
        stop_started.set()
        await release_stop.wait()
        backend.stopped_sessions += 1

    backend.stop_session = mock.AsyncMock(side_effect=slow_stop_session)

    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=0.05)
        runtime.start_background_reaper()

    same_id_task: asyncio.Task[dict] | None = None
    try:
        await runtime.create_session(_make_spec("slow"))
        runtime._sessions["slow"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(seconds=1)

        await asyncio.wait_for(stop_started.wait(), timeout=1)
        assert "slow" not in runtime._sessions
        assert "slow" in runtime._closing_session_tasks

        fresh = await asyncio.wait_for(
            runtime.create_session(_make_spec("fresh", persistent=True)),
            timeout=0.2,
        )
        assert fresh["session_id"] == "fresh"

        same_id_task = asyncio.create_task(runtime.create_session(_make_spec("slow")))
        await asyncio.sleep(0.05)
        assert not same_id_task.done()

        release_stop.set()
        recreated = await asyncio.wait_for(same_id_task, timeout=1)

        assert recreated["session_id"] == "slow"
        assert recreated["backend_session_id"] == "fake-3"
        assert "slow" not in runtime._closing_session_tasks
        backend.stop_session.assert_awaited_once()
    finally:
        release_stop.set()
        if same_id_task is not None and not same_id_task.done():
            same_id_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await same_id_task
        await runtime.stop_background_reaper()


@pytest.mark.anyio
async def test_background_reaper_skips_active_execute(logger):
    """An in-flight execute() protects its session from TTL cleanup."""
    backend = FakeBackend(logger)
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_exec(
        session: BoxSessionInfo, spec: BoxSpec
    ) -> BoxExecutionResult:
        backend.exec_calls.append((session.backend_session_id, spec.cmd))
        started.set()
        await release.wait()
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=backend.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="done",
            stderr="",
            duration_ms=100,
        )

    backend.exec = blocking_exec

    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=0.05)
        runtime.start_background_reaper()

    task = asyncio.create_task(runtime.execute(_make_spec("busy", cmd="sleep")))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        async with runtime._lock:
            runtime._sessions["busy"].info.last_used_at = dt.datetime.now(
                _UTC
            ) - dt.timedelta(seconds=1)
            assert runtime._active_exec_counts["busy"] == 1

        await asyncio.sleep(0.15)

        assert "busy" in runtime._sessions
        backend.stop_session.assert_not_awaited()

        release.set()
        result = await task
        assert result.status == BoxExecutionStatus.COMPLETED
        assert not runtime._active_exec_counts
    finally:
        release.set()
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        await runtime.stop_background_reaper()


@pytest.mark.anyio
async def test_execute_cancel_clears_active_counter(logger):
    """execute() must release active counters even on asyncio cancellation."""
    backend = FakeBackend(logger)
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_exec(
        session: BoxSessionInfo, spec: BoxSpec
    ) -> BoxExecutionResult:
        started.set()
        await release.wait()
        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=backend.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=0,
        )

    backend.exec = blocking_exec

    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])

    task = asyncio.create_task(runtime.execute(_make_spec("cancel", cmd="sleep")))
    await asyncio.wait_for(started.wait(), timeout=1)
    assert runtime._active_exec_counts["cancel"] == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not runtime._active_exec_counts
    assert "cancel" not in runtime._sessions
    backend.stop_session.assert_awaited_once()


@pytest.mark.anyio
async def test_cancelling_queued_execute_preserves_running_session(logger):
    backend = FakeBackend(logger)
    started = asyncio.Event()
    release = asyncio.Event()
    original_exec = backend.exec

    async def blocking_exec(session, spec):
        started.set()
        await release.wait()
        return await original_exec(session, spec)

    backend.exec = blocking_exec
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
    running = asyncio.create_task(runtime.execute(_make_spec("shared")))
    await started.wait()
    old_session = runtime._sessions["shared"]
    queued = asyncio.create_task(runtime.execute(_make_spec("shared")))
    await _wait_until(lambda: runtime._active_exec_counts["shared"] == 2)

    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    assert runtime._sessions["shared"] is old_session
    assert not old_session.closing
    assert runtime._active_exec_counts["shared"] == 1
    backend.stop_session.assert_not_awaited()

    release.set()
    assert (await running).ok
    assert backend.exec_calls == [("fake-1", "echo hi")]


@pytest.mark.anyio
@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
async def test_interrupted_execute_fences_queued_work_before_unlock(logger, interrupt):
    backend = FakeBackend(logger)
    started = asyncio.Event()
    release = asyncio.Event()
    entered_commands = []
    original_exec = backend.exec

    async def blocking_exec(session, spec):
        entered_commands.append(spec.cmd)
        if spec.cmd == "blocked":
            started.set()
            await release.wait()
            result = await original_exec(session, spec)
            return result.model_copy(update={"status": BoxExecutionStatus.TIMED_OUT})
        return await original_exec(session, spec)

    backend.exec = blocking_exec
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
    other = await runtime.create_session(_make_spec("other"))
    running = asyncio.create_task(runtime.execute(_make_spec("shared", cmd="blocked")))
    await started.wait()
    old_session = runtime._sessions["shared"]
    queued = asyncio.create_task(runtime.execute(_make_spec("shared", cmd="queued")))
    await _wait_until(lambda: runtime._active_exec_counts["shared"] == 2)

    # Hold the global lock so retirement cannot hide a missing execution fence.
    async with runtime._lock:
        if interrupt == "cancel":
            running.cancel()
        else:
            release.set()
        await asyncio.wait_for(old_session.lock.acquire(), timeout=1)
        old_session.lock.release()
        assert old_session.closing
        assert entered_commands == ["blocked"]

    with pytest.raises(BoxSessionNotFoundError):
        await queued
    if interrupt == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await running
    else:
        assert (await running).status == BoxExecutionStatus.TIMED_OUT
    assert "shared" not in runtime._sessions
    backend.stop_session.assert_awaited_once_with(old_session.info)
    assert (
        runtime._sessions["other"].info.backend_session_id
        == other["backend_session_id"]
    )

    assert (await runtime.execute(_make_spec("shared", cmd="fresh"))).ok
    assert (
        runtime._sessions["shared"].info.backend_session_id
        != old_session.info.backend_session_id
    )
    assert entered_commands == ["blocked", "fresh"]


@pytest.mark.anyio
@pytest.mark.parametrize("retry", ["acquire", "delete"])
async def test_failed_cleanup_retains_fence_and_can_be_retried(logger, retry):
    backend = FakeBackend(logger)
    backend.stop_session.side_effect = RuntimeError("cannot stop container")
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], max_sessions=1)
    await runtime.create_session(_make_spec("failed"))
    old_session = runtime._sessions["failed"]

    with pytest.raises(BoxError, match="cannot stop container"):
        await runtime.delete_session("failed")
    assert runtime._sessions["failed"] is old_session
    assert old_session.closing
    assert not runtime._closing_session_tasks
    with pytest.raises(BoxCapacityExceededError):
        await runtime.create_session(_make_spec("other"))
    with pytest.raises(BoxError, match="cannot stop container"):
        await asyncio.wait_for(runtime.create_session(_make_spec("failed")), timeout=1)
    assert backend.started_sessions == 1
    assert backend.exec_calls == []

    backend.stop_session.side_effect = backend._stop_session
    if retry == "delete":
        await runtime.delete_session("failed")
    fresh = await runtime.create_session(_make_spec("failed"))
    assert fresh["backend_session_id"] != old_session.info.backend_session_id
    assert not runtime._sessions["failed"].closing


@pytest.mark.anyio
async def test_cancelled_execute_keeps_cancellation_when_cleanup_fails(logger):
    backend = FakeBackend(logger)
    started = asyncio.Event()

    async def blocking_exec(session, spec):
        started.set()
        await asyncio.Event().wait()

    backend.exec = blocking_exec
    backend.stop_session.side_effect = RuntimeError("cannot stop container")
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
    running = asyncio.create_task(runtime.execute(_make_spec("failed")))
    await started.wait()
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert runtime._sessions["failed"].closing
    assert not runtime._active_exec_counts
    backend.stop_session.assert_awaited_once()


@pytest.mark.anyio
async def test_managed_process_cleanup_failure_still_stops_backend(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
    await runtime.create_session(_make_spec("managed"))
    await runtime.start_managed_process(
        "managed", BoxManagedProcessSpec(command="daemon")
    )
    with mock.patch.object(
        runtime,
        "_terminate_managed_process",
        side_effect=RuntimeError("terminate failed"),
    ):
        with pytest.raises(BoxError, match="Failed to terminate managed processes"):
            await runtime.delete_session("managed")
    backend.stop_session.assert_awaited_once()
    assert runtime._sessions["managed"].closing
    assert "default" in runtime._sessions["managed"].managed_processes
    await runtime.delete_session("managed")
    assert "managed" not in runtime._sessions


@pytest.mark.anyio
async def test_background_reaper_skips_running_managed_process(logger):
    """An idle session with a running managed process is not TTL-reaped."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=0.05)
        runtime.start_background_reaper()

    try:
        await runtime.create_session(_make_spec("managed"))
        await runtime.start_managed_process(
            "managed", BoxManagedProcessSpec(command="daemon")
        )
        await _settle()
        runtime._sessions["managed"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(seconds=1)

        await asyncio.sleep(0.15)

        assert "managed" in runtime._sessions
        backend.stop_session.assert_not_awaited()

        await runtime.stop_managed_process("managed", "default")
        if "managed" in runtime._sessions:
            runtime._sessions["managed"].info.last_used_at = dt.datetime.now(
                _UTC
            ) - dt.timedelta(seconds=1)

        await _wait_until(
            lambda: (
                "managed" not in runtime._sessions
                and backend.stop_session.await_count == 1
            )
        )
        backend.stop_session.assert_awaited_once()
    finally:
        if "managed" in runtime._sessions:
            managed_process = runtime._sessions["managed"].managed_processes.get(
                "default"
            )
            if managed_process is not None and managed_process.is_running:
                await runtime.stop_managed_process("managed", "default")
        await runtime.stop_background_reaper()


# ── delete_session / shutdown ───────────────────────────────────────────


@pytest.mark.anyio
async def test_delete_unknown_session_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxSessionNotFoundError):
            await runtime.delete_session("nope")


@pytest.mark.anyio
async def test_delete_session_stops_backend(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("del"))
        await runtime.delete_session("del")

    assert "del" not in runtime._sessions
    backend.stop_session.assert_awaited_once()


@pytest.mark.anyio
async def test_shutdown_drops_all_sessions_including_persistent(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("ephemeral"))
        await runtime.create_session(_make_spec("persist", persistent=True))
        await runtime.shutdown()

    assert "ephemeral" not in runtime._sessions
    assert "persist" not in runtime._sessions
    assert backend.stopped_sessions == 2


@pytest.mark.anyio
async def test_shutdown_does_not_stop_background_reaper(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=0.05)
        await runtime.initialize()

    try:
        reaper_task = runtime._reaper_task
        assert reaper_task is not None

        await runtime.create_session(_make_spec("before-shutdown"))
        await runtime.shutdown()

        assert runtime._reaper_task is reaper_task
        assert not reaper_task.done()

        await runtime.create_session(_make_spec("after-shutdown"))
        runtime._sessions["after-shutdown"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(seconds=1)

        await _wait_until(
            lambda: (
                "after-shutdown" not in runtime._sessions
                and backend.stopped_sessions == 2
            )
        )
        assert backend.stopped_sessions == 2
    finally:
        await runtime.stop_background_reaper()


# ── get_status / get_backend_info / get_session(s) ──────────────────────


@pytest.mark.anyio
async def test_get_status_reports_sessions_and_ttl(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=42)
        await runtime.create_session(_make_spec("a"))
        await runtime.create_session(_make_spec("b"))
        status = await runtime.get_status()

    assert status["active_sessions"] == 2
    assert status["session_ttl_sec"] == 42
    assert status["managed_processes"] == 0
    assert status["backend"] == {"name": "fake", "available": True}


@pytest.mark.anyio
async def test_get_backend_info_unavailable(logger):
    """is_available raising → reported as unavailable."""
    backend = FakeBackend(logger)
    backend.is_available = mock.AsyncMock(side_effect=RuntimeError("probe failed"))
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        runtime._backend = backend
        info = await runtime.get_backend_info()
    assert info == {"name": "fake", "available": False}


@pytest.mark.anyio
async def test_get_backend_info_none_when_no_backend(logger):
    """All backends unavailable → backend info reports name None / not available."""
    backend = FakeBackend(logger, available=False)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        info = await runtime.get_backend_info()
    assert info == {"name": None, "available": False}


@pytest.mark.anyio
async def test_get_sessions_and_get_session(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("one"))
        sessions = runtime.get_sessions()
        single = runtime.get_session("one")

    assert len(sessions) == 1
    assert single["session_id"] == "one"
    assert "managed_processes" not in single  # none started


@pytest.mark.anyio
async def test_workspace_session_index_avoids_global_scan_and_cleans_up(logger):
    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError("Workspace lookup scanned every Box session")

        def values(self):
            raise AssertionError("Workspace lookup scanned every Box session")

    backend = FakeBackend(logger)
    workspace_a = ActionContext(
        instance_uuid="instance",
        workspace_uuid="workspace-a",
        placement_generation=1,
    )
    workspace_b = workspace_a.model_copy(update={"workspace_uuid": "workspace-b"})
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(
            _make_spec("session-a"),
            action_context=workspace_a,
        )
        await runtime.create_session(
            _make_spec("session-b"),
            action_context=workspace_b,
        )
        runtime._sessions = NoGlobalIterationDict(runtime._sessions)

        sessions_a = runtime.get_sessions_for_workspace(workspace_a)
        assert [session["session_id"] for session in sessions_a] == ["session-a"]

        await runtime.delete_session("session-a")
        assert runtime.get_sessions_for_workspace(workspace_a) == []
        assert ("instance", "workspace-a") not in runtime._session_ids_by_workspace

        await runtime.delete_session("session-b")
        assert runtime._session_ids_by_workspace == {}


def test_get_session_unknown_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxSessionNotFoundError):
            runtime.get_session("ghost")


# ── _get_backend / backend selection ────────────────────────────────────


@pytest.mark.anyio
async def test_get_backend_selects_first_available(logger):
    unavailable = FakeBackend(logger, name="fake", available=False)
    available = FakeBackend(logger, name="other", available=True)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[unavailable, available])
        selected = await runtime._get_backend()
    assert selected is available


@pytest.mark.anyio
async def test_get_backend_raises_when_none_available(logger):
    backend = FakeBackend(logger, available=False)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxBackendUnavailableError):
            await runtime._get_backend()


@pytest.mark.anyio
async def test_get_backend_caches_selection(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        first = await runtime._get_backend()
        second = await runtime._get_backend()
    assert first is second is backend
    # initialize() only runs during the first selection.
    assert backend.initialize_calls == 1


@pytest.mark.anyio
async def test_select_backend_forced_local_picks_local_name(logger):
    """box.backend=local fans out to local container backends."""
    nsjail = FakeBackend(logger, name="nsjail", available=True)
    e2b = FakeBackend(logger, name="e2b", available=True)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[e2b, nsjail])
        runtime.init({"backend": "local"})
        selected = await runtime._select_backend()
    assert selected is nsjail


@pytest.mark.anyio
async def test_select_backend_forced_local_no_local_returns_none(logger):
    e2b = FakeBackend(logger, name="e2b", available=True)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[e2b])
        runtime.init({"backend": "local"})
        selected = await runtime._select_backend()
    assert selected is None


@pytest.mark.anyio
async def test_select_backend_probe_exception_skips_backend(logger):
    """A backend whose probe raises is skipped in favour of the next one."""
    bad = FakeBackend(logger, name="bad", available=True)
    bad.is_available = mock.AsyncMock(side_effect=RuntimeError("probe blew up"))
    good = FakeBackend(logger, name="good", available=True)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[bad, good])
        selected = await runtime._select_backend()
    assert selected is good


# ── managed processes ───────────────────────────────────────────────────


async def _settle():
    """Yield control so background tasks (drain/watch) get a chance to run."""
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.mark.anyio
async def test_start_managed_process_creates_and_reports_running(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("mp"))
        info = await runtime.start_managed_process(
            "mp", BoxManagedProcessSpec(command="sleep", args=["1"])
        )
        await _settle()

        assert info["session_id"] == "mp"
        assert info["process_id"] == "default"
        assert info["status"] == BoxManagedProcessStatus.RUNNING.value

        # get_managed_process returns the same view.
        got = runtime.get_managed_process("mp", "default")
        assert got["command"] == "sleep"
        assert got["args"] == ["1"]

        # get_session surfaces the managed process.
        session = runtime.get_session("mp")
        assert "managed_processes" in session
        assert "managed_process" in session  # 'default' alias
        assert session["managed_process"]["status"] == (
            BoxManagedProcessStatus.RUNNING.value
        )

        # get_status counts the running managed process.
        status = await runtime.get_status()
        assert status["managed_processes"] == 1

        # Clean up: stop the process and its background tasks.
        await runtime.stop_managed_process("mp", "default")


@pytest.mark.anyio
async def test_start_managed_process_unknown_session_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxSessionNotFoundError):
            await runtime.start_managed_process(
                "ghost", BoxManagedProcessSpec(command="sleep")
            )


@pytest.mark.anyio
async def test_start_managed_process_replaces_running_one(logger):
    """Starting a process when one is already running terminates the old one."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("mp2"))
        await runtime.start_managed_process(
            "mp2", BoxManagedProcessSpec(command="first")
        )
        await _settle()
        first_proc = backend.last_process

        await runtime.start_managed_process(
            "mp2", BoxManagedProcessSpec(command="second")
        )
        await _settle()

        # The stale process was terminated before the new one started.
        assert first_proc.returncode is not None
        got = runtime.get_managed_process("mp2", "default")
        assert got["command"] == "second"

        await runtime.stop_managed_process("mp2", "default")


@pytest.mark.anyio
async def test_get_managed_process_not_found_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("mp3"))
        with pytest.raises(BoxManagedProcessNotFoundError):
            runtime.get_managed_process("mp3", "default")


def test_get_managed_process_unknown_session_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxSessionNotFoundError):
            runtime.get_managed_process("ghost", "default")


@pytest.mark.anyio
async def test_stop_managed_process_terminates_and_marks_exited(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("mp4"))
        await runtime.start_managed_process(
            "mp4", BoxManagedProcessSpec(command="daemon")
        )
        await _settle()
        proc = backend.last_process

        await runtime.stop_managed_process("mp4", "default")

        assert proc.returncode is not None
        # The process entry was removed from the session.
        with pytest.raises(BoxManagedProcessNotFoundError):
            runtime.get_managed_process("mp4", "default")


@pytest.mark.anyio
async def test_stop_managed_process_unknown_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("mp5"))
        with pytest.raises(BoxManagedProcessNotFoundError):
            await runtime.stop_managed_process("mp5", "default")


@pytest.mark.anyio
async def test_stop_managed_process_unknown_session_raises(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        with pytest.raises(BoxSessionNotFoundError):
            await runtime.stop_managed_process("ghost", "default")


@pytest.mark.anyio
async def test_watch_managed_process_marks_exit_on_natural_finish(logger):
    """When the underlying process exits, the watcher records the exit code."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("mp6"))
        await runtime.start_managed_process(
            "mp6", BoxManagedProcessSpec(command="quickexit")
        )
        await _settle()

        proc = backend.last_process
        proc.finish(code=3)
        await _settle()

        got = runtime.get_managed_process("mp6", "default")
        assert got["status"] == BoxManagedProcessStatus.EXITED.value
        assert got["exit_code"] == 3


@pytest.mark.anyio
async def test_reap_skips_session_with_running_managed_process(logger):
    """An idle session is NOT reaped while it has a running managed process."""
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], session_ttl_sec=60)
        await runtime.create_session(_make_spec("mp7"))
        await runtime.start_managed_process(
            "mp7", BoxManagedProcessSpec(command="daemon")
        )
        await _settle()
        runtime._sessions["mp7"].info.last_used_at = dt.datetime.now(
            _UTC
        ) - dt.timedelta(seconds=999)

        async with runtime._lock:
            await runtime._reap_expired_sessions_locked()

        assert "mp7" in runtime._sessions  # protected by running process
        await runtime.stop_managed_process("mp7", "default")


@pytest.mark.anyio
async def test_session_memory_change_is_a_conflict(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("memory", memory_mb=256))
        with pytest.raises(BoxSessionConflictError, match="memory_mb=256"):
            await runtime.create_session(_make_spec("memory", memory_mb=512))
        await runtime.shutdown()


def test_relative_allowed_mount_root_is_resolved_from_working_directory(
    logger, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    config = {
        "local": {
            "host_root": "./data/box",
            "default_workspace": "",
            "allowed_mount_roots": ["./data/box", "/tmp"],
        }
    }
    with mock.patch("os.getenv", return_value=json.dumps(config)):
        runtime = BoxRuntime(logger, backends=[FakeBackend(logger)])
        runtime._ensure_default_workspace()

    assert (tmp_path / "data/box/default").is_dir()
    assert runtime._allowed_mount_roots()[0] == str((tmp_path / "data/box").resolve())


@pytest.mark.anyio
async def test_session_capacity_is_enforced(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], max_sessions=1)
        await runtime.create_session(_make_spec("one"))
        with pytest.raises(BoxCapacityExceededError, match="capacity"):
            await runtime.create_session(_make_spec("two"))
        await runtime.shutdown()


@pytest.mark.anyio
async def test_closing_session_still_counts_toward_capacity(logger):
    backend = FakeBackend(logger)
    stop_started = asyncio.Event()
    release_stop = asyncio.Event()

    async def slow_stop_session(session: BoxSessionInfo):
        stop_started.set()
        await release_stop.wait()

    backend.stop_session = mock.AsyncMock(side_effect=slow_stop_session)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend], max_sessions=1)
        await runtime.create_session(_make_spec("one"))
        delete_task = asyncio.create_task(runtime.delete_session("one"))
        await stop_started.wait()

        with pytest.raises(BoxCapacityExceededError, match="capacity"):
            await runtime.create_session(_make_spec("two"))

        release_stop.set()
        await delete_task
        created = await runtime.create_session(_make_spec("two"))
        assert created["session_id"] == "two"
        await runtime.shutdown()


@pytest.mark.anyio
async def test_different_sessions_start_without_global_io_lock(logger):
    backend = FakeBackend(logger)
    original_start = backend.start_session
    both_entered = asyncio.Event()
    release = asyncio.Event()
    entered = 0

    async def blocked_start(spec):
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        await release.wait()
        return await original_start(spec)

    backend.start_session = mock.AsyncMock(side_effect=blocked_start)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        first = asyncio.create_task(runtime.create_session(_make_spec("first")))
        second = asyncio.create_task(runtime.create_session(_make_spec("second")))
        await asyncio.wait_for(both_entered.wait(), timeout=1)
        release.set()
        await asyncio.gather(first, second)
        await runtime.shutdown()


@pytest.mark.anyio
async def test_delete_during_managed_process_start_leaves_no_orphan(logger):
    backend = FakeBackend(logger)
    entered = asyncio.Event()
    release = asyncio.Event()
    process = FakeProcess()

    async def blocked_start(session, spec):
        entered.set()
        await release.wait()
        return process

    backend.start_managed_process = mock.AsyncMock(side_effect=blocked_start)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        await runtime.create_session(_make_spec("race"))
        starting = asyncio.create_task(
            runtime.start_managed_process(
                "race", BoxManagedProcessSpec(command="daemon")
            )
        )
        await entered.wait()
        deleting = asyncio.create_task(runtime.delete_session("race"))
        await asyncio.sleep(0)
        release.set()
        await starting
        await deleting

    assert "race" not in runtime._sessions
    process.terminate.assert_called_once()
    backend.stop_session.assert_awaited_once()


@pytest.mark.anyio
async def test_delete_waits_for_inflight_session_creation(logger):
    backend = FakeBackend(logger)
    original_start = backend.start_session
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked_start(spec):
        entered.set()
        await release.wait()
        return await original_start(spec)

    backend.start_session = mock.AsyncMock(side_effect=blocked_start)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(logger, backends=[backend])
        creating = asyncio.create_task(
            runtime.create_session(_make_spec("create-race"))
        )
        await entered.wait()
        deleting = asyncio.create_task(runtime.delete_session("create-race"))
        await asyncio.sleep(0)
        release.set()
        await creating
        await deleting

    assert "create-race" not in runtime._sessions
    backend.stop_session.assert_awaited_once()


@pytest.mark.anyio
async def test_managed_process_capacity_and_completed_retention(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(
            logger,
            backends=[backend],
            max_managed_processes=1,
            completed_process_retention_sec=0,
        )
        await runtime.create_session(_make_spec("p1"))
        await runtime.create_session(_make_spec("p2"))
        await runtime.start_managed_process(
            "p1", BoxManagedProcessSpec(command="daemon")
        )
        with pytest.raises(BoxCapacityExceededError, match="capacity"):
            await runtime.start_managed_process(
                "p2", BoxManagedProcessSpec(command="daemon")
            )

        backend.last_process.finish(0)
        await _wait_until(lambda: not runtime._sessions["p1"].managed_processes)
        await runtime.start_managed_process(
            "p2", BoxManagedProcessSpec(command="daemon")
        )
        await runtime.shutdown()


@pytest.mark.anyio
async def test_completed_process_diagnostics_are_globally_bounded(logger):
    backend = FakeBackend(logger)
    with mock.patch("os.getenv", return_value=""):
        runtime = BoxRuntime(
            logger,
            backends=[backend],
            max_completed_processes=1,
            completed_process_retention_sec=300,
        )
        await runtime.create_session(_make_spec("bounded"))
        await runtime.start_managed_process(
            "bounded", BoxManagedProcessSpec(process_id="one", command="true")
        )
        first = backend.last_process
        first.finish(0)
        await _wait_until(
            lambda: runtime._sessions["bounded"].managed_processes["one"].exit_code == 0
        )

        await runtime.start_managed_process(
            "bounded", BoxManagedProcessSpec(process_id="two", command="true")
        )
        second = backend.last_process
        second.finish(0)
        await _wait_until(
            lambda: "one" not in runtime._sessions["bounded"].managed_processes
        )

        assert set(runtime._sessions["bounded"].managed_processes) == {"two"}
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_capacity_and_reuse_are_atomic_at_full_capacity(logger):
    from langbot_plugin.box.tenancy import namespace_session_id

    context = ActionContext(
        instance_uuid="instance", workspace_uuid="workspace", placement_generation=1
    )
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger=logger, backends=[backend], max_sessions=1)
    await runtime.initialize()
    try:
        spec = BoxSpec(session_id=namespace_session_id(context, "shared"))
        first, second = await asyncio.gather(
            runtime.create_session(spec, action_context=context),
            runtime.create_session(spec, action_context=context),
        )
        assert first["backend_session_id"] == second["backend_session_id"]
        assert await runtime.get_capacity(context) == {
            "limit": 1,
            "used": 1,
            "remaining": 0,
        }
        await runtime.create_session(spec, action_context=context)
        with pytest.raises(BoxCapacityExceededError):
            await runtime.create_session(
                BoxSpec(session_id=namespace_session_id(context, "another")),
                action_context=context,
            )
    finally:
        await runtime.shutdown()


@pytest.mark.anyio
async def test_fixed_mount_conflict_preserves_existing_session(logger):
    backend = FakeBackend(logger)
    runtime = BoxRuntime(logger, backends=[backend])
    original = _make_spec("fixed", cmd="before")
    await runtime.execute(original)
    changed = original.model_copy(
        update={
            "extra_mounts": [
                BoxMountSpec(host_path="/tmp/package", mount_path="/package", mode="ro")
            ]
        }
    )
    with pytest.raises(BoxSessionConflictError, match="existing session was preserved"):
        await runtime.execute(changed)
    await runtime.execute(original.model_copy(update={"cmd": "after"}))
    assert backend.started_sessions == 1
    backend.stop_session.assert_not_awaited()
    await runtime.shutdown()
