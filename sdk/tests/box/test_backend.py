"""Unit tests for the Docker (CLI) sandbox backend.

These tests do NOT require Docker to be installed.  ``asyncio.create_subprocess_exec``
is mocked with a fake process that exposes ``wait()``/``returncode`` plus
``stdout``/``stderr`` stream readers (and ``stdin``/``communicate`` for managed
processes), so the real ``docker`` binary is never invoked.  The tests assert
the exact argv lists handed to Docker, the returned ``BoxSessionInfo`` /
``BoxExecutionResult`` fields, and the security-validation path.
"""

from __future__ import annotations

import asyncio
import logging
import os
from types import SimpleNamespace
from unittest import mock

import pytest

from langbot_plugin.box.backend import (
    CLISandboxBackend,
    DockerBackend,
    _CommandResult,
)
from langbot_plugin.box.errors import BoxError, BoxValidationError
from langbot_plugin.box.models import (
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxManagedProcessSpec,
    BoxMountSpec,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)


@pytest.fixture
def logger():
    return logging.getLogger("test.docker")


@pytest.fixture
def backend(logger):
    b = DockerBackend(logger=logger)
    b.instance_id = "inst-test"
    return b


@pytest.fixture
def session():
    return BoxSessionInfo(
        session_id="sess1",
        backend_name="docker",
        backend_session_id="langbot-box-sess1-abcd1234",
        image="rockchin/langbot-sandbox:latest",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )


class _FakeStream:
    """Minimal async stream reader yielding *data* in chunks, then EOF."""

    def __init__(self, data: bytes, chunk_size: int | None = None):
        if chunk_size is None:
            self._chunks = [data] if data else []
        else:
            self._chunks = [
                data[i : i + chunk_size] for i in range(0, len(data), chunk_size)
            ]
        self._index = 0

    async def read(self, _n: int = -1) -> bytes:
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


class _FakeProcess:
    """Fake asyncio subprocess used by ``_run_command`` / managed processes."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        hang: bool = False,
    ):
        self.returncode = returncode
        self.stdout = _FakeStream(stdout)
        self.stderr = _FakeStream(stderr)
        self.stdin = mock.MagicMock()
        self._hang = hang
        self.killed = False
        self.terminated = False
        self.wait_started = asyncio.Event()

    async def wait(self):
        self.wait_started.set()
        if self._hang:
            # Never completes on its own; ``asyncio.wait_for`` will time it out.
            await asyncio.sleep(3600)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self._hang = False

    def kill(self):
        self.killed = True
        self._hang = False

    async def communicate(self, _input=None):
        return (b"", b"")


def _patch_exec(proc: _FakeProcess):
    """Patch ``asyncio.create_subprocess_exec`` to return *proc* and capture argv."""
    mock_exec = mock.AsyncMock(return_value=proc)
    return mock.patch("asyncio.create_subprocess_exec", mock_exec), mock_exec


def _argv_of(mock_exec: mock.AsyncMock, call_index: int = 0) -> list[str]:
    return list(mock_exec.call_args_list[call_index].args)


def _value_after(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def _all_values_after(argv: list[str], flag: str) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == flag]


# ── backend identity ──────────────────────────────────────────────────


def test_backend_name_and_command(backend):
    assert backend.name == "docker"
    assert backend.command == "docker"


def test_configure_logs_when_docker_cpu_limit_is_disabled(backend, caplog):
    with caplog.at_level(logging.WARNING, logger=backend.logger.name):
        backend.configure({"cpu_limit_enabled": False})

    assert "Docker sandbox CPU limit is disabled by config" in caplog.text
    assert "containers will be started without --cpus" in caplog.text


# ── is_available ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_is_available_no_binary(backend):
    with mock.patch("shutil.which", return_value=None):
        assert await backend.is_available() is False


@pytest.mark.anyio
async def test_is_available_binary_ok(backend):
    proc = _FakeProcess(returncode=0, stdout=b"docker info ok")
    patcher, mock_exec = _patch_exec(proc)
    with mock.patch("shutil.which", return_value="/usr/bin/docker"), patcher:
        assert await backend.is_available() is True

    argv = _argv_of(mock_exec)
    assert argv == ["docker", "info"]


@pytest.mark.anyio
async def test_is_available_info_nonzero(backend):
    proc = _FakeProcess(returncode=1, stderr=b"cannot connect")
    patcher, _ = _patch_exec(proc)
    with mock.patch("shutil.which", return_value="/usr/bin/docker"), patcher:
        assert await backend.is_available() is False


# ── start_session: argv construction ──────────────────────────────────


@pytest.mark.anyio
async def test_start_session_basic_argv_and_info(backend):
    proc = _FakeProcess(returncode=0, stdout=b"containerid\n")
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(session_id="My Session!", cmd="echo hi")

    with patcher:
        info = await backend.start_session(spec)

    argv = _argv_of(mock_exec)

    # Base command.
    assert argv[:3] == ["docker", "run", "-d"]
    # Non-persistent -> --rm.
    assert "--rm" in argv

    # Name + labels.
    container_name = _value_after(argv, "--name")
    assert container_name.startswith("langbot-box-")
    labels = _all_values_after(argv, "--label")
    assert "langbot.box=true" in labels
    assert f"langbot.session_id={spec.session_id}" in labels
    assert "langbot.box.instance_id=inst-test" in labels

    # Network OFF -> --network none.
    assert _value_after(argv, "--network") == "none"

    # Resource limits.
    assert _value_after(argv, "--cpus") == "1.0"
    assert _value_after(argv, "--memory") == "512m"
    assert _value_after(argv, "--pids-limit") == "128"

    # read_only_rootfs default True -> --read-only + tmpfs.
    assert "--read-only" in argv
    assert _value_after(argv, "--tmpfs") == "/tmp:size=64m"

    # Tail: image then the long-running shell.
    assert argv[-4:] == [spec.image, "sh", "-lc", "while true; do sleep 3600; done"]

    # Returned session info.
    assert info.session_id == spec.session_id
    assert info.backend_name == "docker"
    assert info.backend_session_id == container_name
    assert info.image == spec.image
    assert info.network == BoxNetworkMode.OFF
    assert info.read_only_rootfs is True
    assert info.persistent is False
    assert info.created_at == info.last_used_at


@pytest.mark.anyio
async def test_start_session_persistent_no_rm(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(session_id="persist", cmd="x", persistent=True)

    with patcher:
        info = await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    assert "--rm" not in argv
    assert info.persistent is True


@pytest.mark.anyio
async def test_start_session_network_on_omits_network_flag(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(session_id="net", cmd="x", network=BoxNetworkMode.ON)

    with patcher:
        info = await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    # ON mode leaves Docker's default network in place: no --network none.
    assert "--network" not in argv
    assert info.network == BoxNetworkMode.ON


@pytest.mark.anyio
async def test_start_session_writable_rootfs_no_readonly(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(session_id="rw-root", cmd="x", read_only_rootfs=False)

    with patcher:
        info = await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    assert "--read-only" not in argv
    assert "--tmpfs" not in argv
    assert info.read_only_rootfs is False


@pytest.mark.anyio
async def test_start_session_custom_resource_limits(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(
        session_id="res",
        cmd="x",
        cpus=2.5,
        memory_mb=1024,
        pids_limit=256,
    )

    with patcher:
        info = await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    assert _value_after(argv, "--cpus") == "2.5"
    assert _value_after(argv, "--memory") == "1024m"
    assert _value_after(argv, "--pids-limit") == "256"
    assert info.cpus == 2.5
    assert info.memory_mb == 1024
    assert info.pids_limit == 256


@pytest.mark.anyio
async def test_start_session_can_disable_docker_cpu_limit(backend):
    backend.configure({"cpu_limit_enabled": False})
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(session_id="no-cpu-limit", cmd="x")

    with patcher:
        await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    assert "--cpus" not in argv
    assert _value_after(argv, "--memory") == "512m"
    assert _value_after(argv, "--pids-limit") == "128"


@pytest.mark.anyio
async def test_start_session_can_disable_docker_cpu_limit_from_string_config(backend):
    backend.configure({"cpu_limit_enabled": "false"})
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(session_id="no-cpu-limit-env", cmd="x")

    with patcher:
        await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    assert "--cpus" not in argv
    assert _value_after(argv, "--memory") == "512m"
    assert _value_after(argv, "--pids-limit") == "128"


@pytest.mark.anyio
async def test_start_session_host_path_mount(backend, tmp_path):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    host_path = tmp_path / "data" / "project"
    spec = BoxSpec(
        session_id="hp",
        cmd="ls",
        host_path=str(host_path),
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/project",
        workdir="/project",
    )

    with patcher:
        info = await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    binds = _all_values_after(argv, "-v")
    assert f"{host_path}:/project:rw" in binds
    assert info.host_path == str(host_path)
    assert info.host_path_mode == BoxHostMountMode.READ_WRITE
    assert info.mount_path == "/project"


@pytest.mark.anyio
async def test_start_session_host_path_readonly_mount(backend, tmp_path):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    host_path = tmp_path / "data" / "source"
    spec = BoxSpec(
        session_id="hp-ro",
        cmd="cat f",
        host_path=str(host_path),
        host_path_mode=BoxHostMountMode.READ_ONLY,
    )

    with patcher:
        await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    binds = _all_values_after(argv, "-v")
    assert f"{host_path}:/workspace:ro" in binds


@pytest.mark.anyio
async def test_start_session_creates_host_path_before_mounting(backend, tmp_path):
    proc = _FakeProcess(returncode=0)
    patcher, _mock_exec = _patch_exec(proc)
    host_path = tmp_path / "box" / "default"
    spec = BoxSpec(session_id="create-host-path", cmd="x", host_path=str(host_path))

    with patcher:
        await backend.start_session(spec)

    assert host_path.is_dir()


@pytest.mark.anyio
async def test_start_session_host_path_none_skips_mount(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(
        session_id="hp-none",
        cmd="ls",
        host_path="/data",
        host_path_mode=BoxHostMountMode.NONE,
    )

    with patcher:
        await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    mounts = [argv[i + 1] for i, arg in enumerate(argv) if arg == "-v"]
    assert len(mounts) == 1
    assert mounts[0].endswith(":/opt/langbot-artifacts:ro")


@pytest.mark.anyio
async def test_start_session_extra_mounts(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(
        session_id="extra",
        cmd="ls",
        extra_mounts=[
            BoxMountSpec(
                host_path="/data/skills/demo",
                mount_path="/workspace/.skills/demo",
                mode=BoxHostMountMode.READ_WRITE,
            ),
            BoxMountSpec(
                host_path="/data/config",
                mount_path="/etc/app",
                mode=BoxHostMountMode.READ_ONLY,
            ),
        ],
    )

    with patcher:
        await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    binds = _all_values_after(argv, "-v")
    assert "/data/skills/demo:/workspace/.skills/demo:rw" in binds
    assert "/data/config:/etc/app:ro" in binds


@pytest.mark.anyio
async def test_start_session_extra_mount_none_mode_skipped(backend):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(
        session_id="extra-none",
        cmd="ls",
        extra_mounts=[
            BoxMountSpec(
                host_path="/data/skip",
                mount_path="/mnt/skip",
                mode=BoxHostMountMode.NONE,
            ),
        ],
    )

    with patcher:
        await backend.start_session(spec)

    argv = _argv_of(mock_exec)
    assert "/data/skip:/mnt/skip:none" not in _all_values_after(argv, "-v")


@pytest.mark.anyio
async def test_start_session_workspace_quota_passthrough(backend):
    proc = _FakeProcess(returncode=0)
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="quota", cmd="x", workspace_quota_mb=2048)

    with patcher:
        info = await backend.start_session(spec)

    # workspace_quota_mb is carried into the returned session info even though
    # the Docker CLI argv does not encode it directly.
    assert info.workspace_quota_mb == 2048


@pytest.mark.anyio
async def test_start_session_calls_security_validation(backend):
    proc = _FakeProcess(returncode=0)
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sec", cmd="x")

    with (
        patcher,
        mock.patch(
            "langbot_plugin.box.backend.validate_sandbox_security"
        ) as mock_validate,
    ):
        await backend.start_session(spec)

    mock_validate.assert_called_once_with(spec)


@pytest.mark.anyio
async def test_start_session_blocked_host_path_raises(backend):
    """A blocked host_path aborts before any subprocess is launched.

    The validation itself is platform-sensitive (it resolves symlinks, e.g.
    ``/etc`` -> ``/private/etc`` on macOS), so we drive the security check
    directly to assert ``start_session`` propagates the rejection.
    """
    spec = BoxSpec(
        session_id="blocked",
        cmd="x",
        host_path="/data/safe",
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/data/safe",
    )

    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    with (
        patcher,
        mock.patch(
            "langbot_plugin.box.backend.validate_sandbox_security",
            side_effect=BoxValidationError(
                "host_path /data/safe is blocked for security"
            ),
        ),
    ):
        with pytest.raises(BoxValidationError):
            await backend.start_session(spec)

    # Validation runs before any subprocess is launched.
    mock_exec.assert_not_called()


def test_validate_sandbox_security_rejects_blocked_path():
    """The security validator rejects blocked host paths (real call)."""
    from langbot_plugin.box.security import validate_sandbox_security

    # Use a path that realpath leaves untouched on every platform by mocking
    # realpath so the test is OS-independent.
    spec = BoxSpec(
        session_id="sec-real",
        cmd="x",
        host_path="/proc",
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/proc",
    )
    with mock.patch("os.path.realpath", return_value="/proc"):
        with pytest.raises(BoxValidationError):
            validate_sandbox_security(spec)


def test_validate_sandbox_security_rejects_blocked_extra_mount_path():
    from langbot_plugin.box.security import validate_sandbox_security

    spec = BoxSpec(
        session_id="sec-extra",
        cmd="x",
        extra_mounts=[
            BoxMountSpec(
                host_path="/etc",
                mount_path="/workspace/etc",
                mode=BoxHostMountMode.READ_ONLY,
            )
        ],
    )
    with mock.patch("os.path.realpath", return_value="/etc"):
        with pytest.raises(
            BoxValidationError, match="extra_mounts.host_path /etc is blocked"
        ):
            validate_sandbox_security(spec)


def test_validate_sandbox_security_allows_safe_path():
    """The security validator passes ordinary host paths."""
    from langbot_plugin.box.security import validate_sandbox_security

    spec = BoxSpec(
        session_id="sec-ok",
        cmd="x",
        host_path="/data/project",
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/data/project",
    )
    with mock.patch("os.path.realpath", return_value="/data/project"):
        validate_sandbox_security(spec)  # should not raise


@pytest.mark.anyio
async def test_start_session_check_failure_raises_boxerror(backend):
    proc = _FakeProcess(returncode=125, stderr=b"docker: image not found")
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="fail", cmd="x")

    with patcher:
        with pytest.raises(BoxError) as exc:
            await backend.start_session(spec)

    assert "docker backend error" in str(exc.value)
    assert "image not found" in str(exc.value)


# ── exec ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_exec_argv_and_completed(backend, session):
    proc = _FakeProcess(returncode=0, stdout=b"hello\n", stderr=b"")
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxSpec(
        session_id="sess1",
        cmd="echo hello",
        workdir="/workspace",
        env={"FOO": "bar", "BAZ": "qux"},
        timeout_sec=15,
    )

    with patcher:
        result = await backend.exec(session, spec)

    argv = _argv_of(mock_exec)
    assert argv[:2] == ["docker", "exec"]

    # Env flags.
    env_values = _all_values_after(argv, "-e")
    assert "FOO=bar" in env_values
    assert "BAZ=qux" in env_values

    # Container id then shell invocation.
    assert argv[-4] == session.backend_session_id
    assert argv[-3:-1] == ["sh", "-lc"]
    assert argv[-1] == backend._build_exec_command("/workspace", "echo hello")

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "hello"
    assert result.stderr == ""
    assert result.backend_name == "docker"
    assert result.session_id == "sess1"
    assert result.ok is True
    assert result.duration_ms >= 0


@pytest.mark.anyio
async def test_exec_truncates_long_cmd_preview_in_log(backend, session):
    # A very long command exercises the >400 char preview-truncation branch.
    long_cmd = "echo " + ("a" * 500)
    proc = _FakeProcess(returncode=0, stdout=b"ok")
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sess1", cmd=long_cmd)

    with patcher:
        result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.COMPLETED


@pytest.mark.anyio
async def test_exec_handles_none_streams(backend, session):
    # When the process exposes no stdout/stderr readers, output is empty.
    proc = _FakeProcess(returncode=0)
    proc.stdout = None
    proc.stderr = None
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sess1", cmd="echo hi")

    with patcher:
        result = await backend.exec(session, spec)

    assert result.stdout == ""
    assert result.stderr == ""
    assert result.exit_code == 0


@pytest.mark.anyio
async def test_exec_nonzero_exit(backend, session):
    proc = _FakeProcess(returncode=2, stdout=b"", stderr=b"boom")
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sess1", cmd="false")

    with patcher:
        result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 2
    assert result.stderr == "boom"
    assert result.ok is False


@pytest.mark.anyio
async def test_exec_timeout(backend, session):
    proc = _FakeProcess(returncode=0, hang=True)
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sess1", cmd="sleep 100", timeout_sec=1)

    # Make wait_for time out immediately rather than waiting 1s.
    async def fake_wait_for(awaitable, timeout):
        # Consume the coroutine to avoid "never awaited" warnings.
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        raise asyncio.TimeoutError

    with patcher, mock.patch("asyncio.wait_for", side_effect=fake_wait_for):
        result = await backend.exec(session, spec)

    assert result.status == BoxExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert "timed out" in result.stderr.lower()
    assert proc.killed is True


@pytest.mark.anyio
async def test_exec_cancellation_terminates_and_reaps_backend_process(
    backend,
    session,
):
    proc = _FakeProcess(returncode=None, hang=True)
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sess1", cmd="sleep 100", timeout_sec=60)

    with patcher:
        task = asyncio.create_task(backend.exec(session, spec))
        await proc.wait_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert proc.terminated is True
    assert proc._hang is False


# ── command builders ──────────────────────────────────────────────────


def test_build_exec_command(backend):
    cmd = backend._build_exec_command("/workspace/sub", "python run.py")
    assert cmd == "mkdir -p /workspace/sub && cd /workspace/sub && python run.py"


def test_build_exec_command_quotes_workdir_with_spaces(backend):
    cmd = backend._build_exec_command("/work space", "ls")
    assert "'/work space'" in cmd
    assert cmd.endswith("&& ls")


def test_build_spawn_command_quotes_args(backend):
    cmd = backend._build_spawn_command("/workspace", "python", ["-c", "print(1)"])
    assert cmd.startswith("mkdir -p /workspace && cd /workspace && exec ")
    assert "python -c 'print(1)'" in cmd


def test_build_container_name_normalizes(backend):
    name = backend._build_container_name("My Session!@#")
    assert name.startswith("langbot-box-")
    # Illegal chars collapsed to hyphens, lowercased; suffix is 8 hex chars.
    body = name[len("langbot-box-") :]
    stem, _, suffix = body.rpartition("-")
    assert len(suffix) == 8
    assert all(c in "0123456789abcdef" for c in suffix)
    assert stem == "my-session"


def test_build_container_name_empty_fallback(backend):
    name = backend._build_container_name("!!!")
    body = name[len("langbot-box-") :]
    stem, _, _ = body.rpartition("-")
    assert stem == "session"


# ── stop_session ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_stop_session_argv(backend, session):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)

    with patcher:
        await backend.stop_session(session)

    argv = _argv_of(mock_exec)
    assert argv == ["docker", "rm", "-f", session.backend_session_id]


@pytest.mark.anyio
async def test_stop_missing_session_cleans_cache_and_preserves_host_mount(
    backend, session, tmp_path
):
    cache = tmp_path / "artifacts"
    cache.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sentinel = workspace / "persistent"
    sentinel.write_text("keep")
    session.host_path = str(workspace)
    backend._artifact_roots[session.backend_session_id] = str(cache)
    backend._run_command = mock.AsyncMock(
        side_effect=[
            _CommandResult(1, "", "remove failed"),
            _CommandResult(0, "another-container\n", ""),
        ]
    )

    await backend.stop_session(session)

    assert not cache.exists()
    assert sentinel.read_text() == "keep"
    assert session.backend_session_id not in backend._artifact_roots
    backend._run_command.assert_awaited_with(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name={session.backend_session_id}",
            "--format",
            "{{.Names}}",
        ],
        timeout_sec=5,
        check=True,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("probe", ["present", "daemon_error", "timeout"])
async def test_stop_failure_preserves_cache_and_reports_error(
    backend, session, tmp_path, probe
):
    cache = tmp_path / "artifacts"
    cache.mkdir()
    backend._artifact_roots[session.backend_session_id] = str(cache)
    probes = {
        "present": _CommandResult(0, session.backend_session_id + "\n", ""),
        "daemon_error": BoxError("daemon unavailable"),
        "timeout": _CommandResult(-1, "", "", timed_out=True),
    }
    backend._run_command = mock.AsyncMock(
        side_effect=[_CommandResult(1, "", "remove failed"), probes[probe]]
    )

    with pytest.raises(BoxError):
        await backend.stop_session(session)

    assert cache.is_dir()
    assert backend._artifact_roots[session.backend_session_id] == str(cache)


# ── is_session_alive ──────────────────────────────────────────────────


@pytest.mark.anyio
async def test_is_session_alive_true(backend, session):
    proc = _FakeProcess(returncode=0, stdout=b"true\n")
    patcher, mock_exec = _patch_exec(proc)

    with patcher:
        alive = await backend.is_session_alive(session)

    argv = _argv_of(mock_exec)
    assert argv == [
        "docker",
        "inspect",
        "-f",
        "{{.State.Running}}",
        session.backend_session_id,
    ]
    assert alive is True


@pytest.mark.anyio
async def test_is_session_alive_false_when_stopped(backend, session):
    proc = _FakeProcess(returncode=0, stdout=b"false\n")
    patcher, _ = _patch_exec(proc)
    with patcher:
        assert await backend.is_session_alive(session) is False


@pytest.mark.anyio
async def test_is_session_alive_false_when_missing(backend, session):
    proc = _FakeProcess(returncode=1, stderr=b"No such object")
    patcher, _ = _patch_exec(proc)
    with patcher:
        assert await backend.is_session_alive(session) is False


# ── cleanup_orphaned_containers ───────────────────────────────────────


@pytest.mark.anyio
async def test_cleanup_orphaned_removes_only_own_instance(backend):
    ps_proc = _FakeProcess(
        returncode=0,
        # Includes a blank line (skipped) plus an unlabeled container ('ccc').
        stdout=b"aaa\tother-instance\n\nbbb\tinst-test\nccc\t\n",
    )
    rm_proc = _FakeProcess(returncode=0)
    mock_exec = mock.AsyncMock(side_effect=[ps_proc, rm_proc])

    with mock.patch("asyncio.create_subprocess_exec", mock_exec):
        await backend.cleanup_orphaned_containers("inst-test")

    # First call lists containers.
    ps_argv = _argv_of(mock_exec, 0)
    assert ps_argv[:4] == ["docker", "ps", "-a", "--filter"]
    assert "label=langbot.box=true" in ps_argv
    assert "label=langbot.box.instance_id=inst-test" in ps_argv

    rm_argv = _argv_of(mock_exec, 1)
    assert rm_argv[:3] == ["docker", "rm", "-f"]
    assert rm_argv[3:] == ["bbb"]


@pytest.mark.anyio
async def test_cleanup_orphaned_handles_line_without_label_field(backend):
    ps_proc = _FakeProcess(returncode=0, stdout=b"ddd\n")
    rm_proc = _FakeProcess(returncode=0)
    mock_exec = mock.AsyncMock(side_effect=[ps_proc, rm_proc])

    with mock.patch("asyncio.create_subprocess_exec", mock_exec):
        await backend.cleanup_orphaned_containers("inst-test")

    assert mock_exec.call_count == 1


@pytest.mark.anyio
async def test_cleanup_orphaned_noop_when_nothing_listed(backend):
    ps_proc = _FakeProcess(returncode=0, stdout=b"")
    mock_exec = mock.AsyncMock(return_value=ps_proc)

    with mock.patch("asyncio.create_subprocess_exec", mock_exec):
        await backend.cleanup_orphaned_containers("inst-test")

    # Only the listing call happened; no rm.
    assert mock_exec.call_count == 1


@pytest.mark.anyio
async def test_cleanup_orphaned_noop_when_all_foreign(backend):
    ps_proc = _FakeProcess(returncode=0, stdout=b"bbb\tother-instance\n")
    mock_exec = mock.AsyncMock(return_value=ps_proc)

    with mock.patch("asyncio.create_subprocess_exec", mock_exec):
        await backend.cleanup_orphaned_containers("inst-test")

    assert mock_exec.call_count == 1


@pytest.mark.anyio
async def test_cleanup_orphaned_ps_failure_is_noop(backend):
    ps_proc = _FakeProcess(returncode=1, stderr=b"daemon down")
    mock_exec = mock.AsyncMock(return_value=ps_proc)

    with mock.patch("asyncio.create_subprocess_exec", mock_exec):
        await backend.cleanup_orphaned_containers("inst-test")

    assert mock_exec.call_count == 1


# ── start_managed_process ─────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_managed_process_argv(backend, session):
    proc = _FakeProcess(returncode=0)
    patcher, mock_exec = _patch_exec(proc)
    spec = BoxManagedProcessSpec(
        command="python",
        args=["-m", "http.server"],
        env={"PORT": "8000"},
        cwd="/workspace",
    )

    with patcher:
        returned = await backend.start_managed_process(session, spec)

    assert returned is proc
    argv = _argv_of(mock_exec)
    assert argv[:3] == ["docker", "exec", "-i"]
    assert "PORT=8000" in _all_values_after(argv, "-e")
    assert argv[-4] == session.backend_session_id
    assert argv[-3:-1] == ["sh", "-lc"]
    assert argv[-1] == backend._build_spawn_command(
        "/workspace", "python", ["-m", "http.server"]
    )

    # Managed processes wire up stdio pipes.
    kwargs = mock_exec.call_args.kwargs
    assert kwargs["stdin"] == asyncio.subprocess.PIPE
    assert kwargs["stdout"] == asyncio.subprocess.PIPE
    assert kwargs["stderr"] == asyncio.subprocess.PIPE


# ── output clipping ───────────────────────────────────────────────────


def test_clip_captured_bytes_within_limit():
    data = b"  hello world  "
    assert DockerBackend._clip_captured_bytes(data, len(data)) == "hello world"


def test_clip_captured_bytes_exceeds_limit():
    result = DockerBackend._clip_captured_bytes(b"hello", 2_000_000, limit=1_000_000)
    assert "clipped" in result
    assert "1000000" in result


@pytest.mark.anyio
async def test_read_stream_none_returns_empty():
    assert await DockerBackend._read_stream(None) == (b"", 0)


@pytest.mark.anyio
async def test_read_stream_caps_at_limit_across_chunks():
    # Two 4-byte chunks with a 5-byte limit: the second chunk arrives after
    # the cap is already reached, exercising the 'remaining <= 0' branch.
    stream = _FakeStream(b"aaaabbbb", chunk_size=4)
    data, total = await DockerBackend._read_stream(stream, limit=5)
    assert total == 8
    assert len(data) == 5
    assert data == b"aaaab"


@pytest.mark.anyio
async def test_exec_clips_large_stdout(backend, session):
    big = b"x" * (2 * 1024 * 1024)  # 2 MB, over the 1 MB cap
    proc = _FakeProcess(returncode=0, stdout=big)
    patcher, _ = _patch_exec(proc)
    spec = BoxSpec(session_id="sess1", cmd="cat big")

    with patcher:
        result = await backend.exec(session, spec)

    assert "clipped" in result.stdout


# ── error formatting ──────────────────────────────────────────────────


def test_format_cli_error_collapses_and_truncates(backend):
    msg = backend._format_cli_error("  some   long\n\nerror  ")
    assert msg == "docker backend error: some long error"

    long = "e" * 400
    truncated = backend._format_cli_error(long)
    assert truncated.endswith("...")
    assert len(truncated) <= len("docker backend error: ") + 300


# ── _CommandResult dataclass ──────────────────────────────────────────


def test_command_result_defaults():
    r = _CommandResult(return_code=0, stdout="out", stderr="err")
    assert r.timed_out is False


@pytest.mark.anyio
async def test_cancelled_container_creation_waits_then_cleans_cache(backend):
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def run(args, **kwargs):
        calls.append(args)
        if args[1] == "run":
            entered.set()
            await release.wait()
        return SimpleNamespace(return_code=0, stdout="", stderr="", timed_out=False)

    with mock.patch.object(backend, "_run_command", side_effect=run):
        task = asyncio.create_task(
            backend.start_session(BoxSpec(session_id="cancel-create"))
        )
        await entered.wait()
        roots = list(backend._artifact_roots.values())
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert calls[-1][1:3] == ["rm", "-f"]
    assert not backend._artifact_roots
    assert all(not os.path.exists(root) for root in roots)


@pytest.mark.anyio
@pytest.mark.parametrize("command_name", ["docker", "podman"])
async def test_availability_coalesces_only_concurrent_probes(logger, command_name):
    backend = CLISandboxBackend(logger, command_name, command_name)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def probe(*args, **kwargs):
        entered.set()
        await release.wait()
        return _CommandResult(0, "ready", "")

    with (
        mock.patch("shutil.which", return_value="/usr/bin/docker"),
        mock.patch.object(backend, "_run_command", side_effect=probe) as command,
    ):
        checks = [asyncio.create_task(backend.is_available()) for _ in range(12)]
        await entered.wait()
        release.set()
        assert await asyncio.gather(*checks) == [True] * 12
        assert command.await_count == 1
        command.side_effect = None
        command.return_value = _CommandResult(1, "", "daemon stopped")
        assert await backend.is_available() is False
        command.return_value = _CommandResult(0, "ready", "")
        assert await backend.is_available() is True
        assert command.await_count == 3


@pytest.mark.anyio
async def test_availability_cancelled_waiter_does_not_cancel_peers(backend):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def probe(*args, **kwargs):
        entered.set()
        await release.wait()
        return _CommandResult(0, "ready", "")

    with (
        mock.patch("shutil.which", return_value="/usr/bin/docker"),
        mock.patch.object(backend, "_run_command", side_effect=probe) as command,
    ):
        first = asyncio.create_task(backend.is_available())
        second = asyncio.create_task(backend.is_available())
        await entered.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert await second is True
        assert command.await_count == 1


@pytest.mark.anyio
async def test_availability_last_cancelled_waiter_reaps_probe(backend):
    entered = asyncio.Event()
    terminated = asyncio.Event()

    async def probe(*args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            terminated.set()

    with (
        mock.patch("shutil.which", return_value="/usr/bin/docker"),
        mock.patch.object(backend, "_run_command", side_effect=probe) as command,
    ):
        checks = [asyncio.create_task(backend.is_available()) for _ in range(2)]
        await entered.wait()
        for task in checks:
            task.cancel()
        results = await asyncio.gather(*checks, return_exceptions=True)
        assert all(isinstance(x, asyncio.CancelledError) for x in results)
        assert terminated.is_set()
        command.side_effect = None
        command.return_value = _CommandResult(0, "ready", "")
        assert await backend.is_available() is True
        assert command.await_count == 2


@pytest.mark.anyio
async def test_availability_probe_failure_is_not_cached(backend):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def probe(*args, **kwargs):
        entered.set()
        await release.wait()
        raise OSError("probe failed")

    with (
        mock.patch("shutil.which", return_value="/usr/bin/docker"),
        mock.patch.object(backend, "_run_command", side_effect=probe) as command,
    ):
        checks = [asyncio.create_task(backend.is_available()) for _ in range(2)]
        await entered.wait()
        release.set()
        results = await asyncio.gather(*checks, return_exceptions=True)
        assert all(isinstance(x, OSError) and str(x) == "probe failed" for x in results)
        assert command.await_count == 1
        command.side_effect = None
        command.return_value = _CommandResult(0, "ready", "")
        assert await backend.is_available() is True


@pytest.mark.anyio
async def test_cancelled_availability_probe_terminates_and_reaps_cli(backend):
    proc = _FakeProcess(returncode=None, hang=True)
    patcher, command = _patch_exec(proc)
    with mock.patch("shutil.which", return_value="/usr/bin/docker"), patcher:
        checks = [asyncio.create_task(backend.is_available()) for _ in range(2)]
        await proc.wait_started.wait()
        for task in checks:
            task.cancel()
        await asyncio.gather(*checks, return_exceptions=True)
    assert command.await_count == 1
    assert proc.terminated is True
    assert proc._hang is False


class _InheritedPipeProcess:
    """Killing the CLI does not close pipes retained by its sudo child."""

    def __init__(self):
        self.returncode = None
        self.wait_started = asyncio.Event()
        self.closed = asyncio.Event()
        self.killed = False
        self.terminated = False
        self.stdout = self.stderr = self
        self._transport = SimpleNamespace(close=self.closed.set)

    async def read(self, _size):
        await self.closed.wait()
        return b""

    async def wait(self):
        self.wait_started.set()
        await self.closed.wait()
        self.returncode = -9
        return self.returncode

    def kill(self):
        self.killed = True

    def terminate(self):
        self.terminated = True


@pytest.mark.anyio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_aborted_exec_stops_box_before_waiting_for_inherited_pipes(
    backend, session, cancelled
):
    proc = _InheritedPipeProcess()

    async def stop(stopped):
        assert stopped is session
        assert proc.killed or proc.terminated
        proc.closed.set()

    backend.stop_session = mock.AsyncMock(side_effect=stop)
    spec = BoxSpec(session_id=session.session_id, cmd="sleep 100", timeout_sec=1)
    with mock.patch("asyncio.create_subprocess_exec", return_value=proc):
        task = asyncio.create_task(backend.exec(session, spec))
        await proc.wait_started.wait()
        if cancelled:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=1)
        else:
            result = await asyncio.wait_for(task, timeout=3)
            assert result.status == BoxExecutionStatus.TIMED_OUT
            assert result.duration_ms < 2500
    backend.stop_session.assert_awaited_once_with(session)
    assert proc.closed.is_set()


@pytest.mark.anyio
async def test_timeout_cleanup_failure_keeps_timeout_and_bounds_pipe_drain(
    backend, session, monkeypatch
):
    proc = _InheritedPipeProcess()
    backend.stop_session = mock.AsyncMock(side_effect=BoxError("remove failed"))
    monkeypatch.setattr("langbot_plugin.box.backend._CLI_CLEANUP_TIMEOUT_SEC", 0.02)
    with mock.patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await asyncio.wait_for(
            backend._run_command(
                ["docker", "exec", session.backend_session_id],
                timeout_sec=0.02,
                check=False,
                timeout_session=session,
            ),
            timeout=0.5,
        )
    assert result.timed_out
    assert "timed out" in result.stderr
    assert "remove failed" in result.stderr
    assert proc.closed.is_set()


@pytest.mark.anyio
async def test_download_permission_fallback_preserves_large_binary(backend, session):
    from langbot_plugin.box.backend import BaseSandboxBackend

    content = bytes(range(256)) * 5000
    process = _FakeProcess(stdout=content)
    with (
        mock.patch.object(
            BaseSandboxBackend, "download_file", side_effect=PermissionError
        ),
        mock.patch(
            "asyncio.create_subprocess_exec", mock.AsyncMock(return_value=process)
        ) as spawn,
    ):
        downloaded = await backend.download_file(
            session, "/workspace/report.bin", len(content)
        )
    assert downloaded == content
    args = spawn.await_args.args
    assert args[:4] == (backend.command, "exec", "-i", session.backend_session_id)
    assert "--user" not in args
    assert "read_workspace_file('/workspace', 'report.bin'" in args[-1]
    process.stdin.close.assert_called_once()


@pytest.mark.anyio
async def test_upload_permission_fallback_uses_stdin_and_checks_content(
    backend, session
):
    from langbot_plugin.box.backend import BaseSandboxBackend

    content = b"\x00binary\xff" * 10000
    process = _FakeProcess()
    process.stdin.drain = mock.AsyncMock()
    with (
        mock.patch.object(
            BaseSandboxBackend, "upload_file", side_effect=PermissionError
        ),
        mock.patch(
            "asyncio.create_subprocess_exec", mock.AsyncMock(return_value=process)
        ) as spawn,
    ):
        await backend.upload_file(
            session, "/workspace/input.bin", content, len(content)
        )
    process.stdin.write.assert_called_once_with(content)
    script = spawn.await_args.args[-1]
    assert "sys.stdin.buffer.read(" in script
    assert "hashlib.sha256(data).hexdigest()" in script
    assert script.index("if len(data)") < script.rindex("write_workspace_file(")


@pytest.mark.anyio
async def test_file_permission_fallback_rejects_oversized_cli_output(backend, session):
    from langbot_plugin.box.backend import BaseSandboxBackend

    with (
        mock.patch.object(
            BaseSandboxBackend, "download_file", side_effect=PermissionError
        ),
        mock.patch(
            "asyncio.create_subprocess_exec",
            mock.AsyncMock(return_value=_FakeProcess(stdout=b"too big")),
        ),
        pytest.raises(BoxError, match="payload size"),
    ):
        await backend.download_file(session, "/workspace/report.bin", 3)


@pytest.mark.anyio
async def test_permission_fallback_waits_for_helper_after_repeated_cancel(
    backend, session
):
    from langbot_plugin.box.backend import BaseSandboxBackend

    started, finish = asyncio.Event(), asyncio.Event()
    process = _FakeProcess(stdout=b"data")

    async def wait():
        started.set()
        await finish.wait()
        return 0

    process.wait = wait
    with (
        mock.patch.object(
            BaseSandboxBackend, "download_file", side_effect=PermissionError
        ),
        mock.patch(
            "asyncio.create_subprocess_exec", mock.AsyncMock(return_value=process)
        ),
    ):
        download = asyncio.create_task(
            backend.download_file(session, "/workspace/report.bin", 100)
        )
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            download.cancel()
            await asyncio.sleep(0)
            assert not download.done()
            download.cancel()
            await asyncio.sleep(0)
            assert not download.done()
            finish.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(download, timeout=1)
        finally:
            finish.set()
            await asyncio.gather(download, return_exceptions=True)
