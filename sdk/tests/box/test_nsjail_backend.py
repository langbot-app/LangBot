"""Unit tests for NsjailBackend.

These tests do NOT require nsjail to be installed – they mock subprocess
calls and filesystem checks to verify argument construction, session
directory management, and cgroup detection logic.
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
from unittest import mock

import pytest

from langbot_plugin.box.nsjail_backend import (
    NsjailBackend,
)
from langbot_plugin.box import nsjail_backend as nsjail_backend_module
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.models import (
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxMountSpec,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)


@pytest.fixture
def logger():
    return logging.getLogger("test.nsjail")


@pytest.fixture
def tmp_base(tmp_path: pathlib.Path):
    return tmp_path / "nsjail-base"


@pytest.fixture
def backend(logger, tmp_base):
    b = NsjailBackend(logger=logger, base_dir=str(tmp_base))
    b.instance_id = "test123"
    return b


# ── is_available ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_is_available_no_binary(backend):
    with mock.patch("shutil.which", return_value=None):
        assert await backend.is_available() is False


@pytest.mark.anyio
async def test_is_available_binary_exists(backend, tmp_base):
    with (
        mock.patch("shutil.which", return_value="/usr/bin/nsjail"),
        mock.patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = mock.AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = mock.AsyncMock(return_value=0)
        mock_exec.return_value = mock_proc

        result = await backend.is_available()
        assert result is True
        assert tmp_base.exists()


@pytest.mark.anyio
async def test_strict_readiness_reports_cgroup_namespace_mount_and_network(
    backend, tmp_path
):
    backend._cgroup_v2_available = True
    expected_probe = {
        "namespace_isolation": True,
        "mount_isolation": True,
        "network_isolation": True,
    }
    with (
        mock.patch.object(
            backend, "is_available", new_callable=mock.AsyncMock, return_value=True
        ),
        mock.patch.object(
            backend,
            "_probe_isolation_readiness",
            new_callable=mock.AsyncMock,
            return_value=expected_probe,
        ) as probe,
    ):
        readiness = await backend.get_readiness(
            workspace_path=str(tmp_path), strict=True
        )

    assert readiness == {
        "available": True,
        "cgroup_v2": True,
        "hard_workspace_quota": False,
        "hard_read_only_mount_quota": False,
        "bounded_ephemeral_storage": False,
        "inode_quota": False,
        **expected_probe,
    }
    probe.assert_awaited_once_with(str(tmp_path))


@pytest.mark.anyio
async def test_isolation_probe_proves_bind_mount_and_distinct_network_namespace(
    backend, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    now = "2024-01-01T00:00:00+00:00"

    async def start_session(spec):
        pathlib.Path(spec.host_path, ".mounted").write_text("readiness")
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name="nsjail",
            backend_session_id=str(tmp_path / "session"),
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            created_at=now,
            last_used_at=now,
        )

    backend.start_session = mock.AsyncMock(side_effect=start_session)
    backend.exec = mock.AsyncMock(return_value=mock.Mock(ok=True, stdout="net:[222]\n"))
    backend.stop_session = mock.AsyncMock()
    with mock.patch("os.readlink", return_value="net:[111]"):
        readiness = await backend._probe_isolation_readiness(str(workspace))

    assert readiness == {
        "namespace_isolation": True,
        "mount_isolation": True,
        "network_isolation": True,
    }
    submitted_spec = backend.start_session.await_args.args[0]
    assert submitted_spec.network is BoxNetworkMode.OFF
    assert submitted_spec.host_path.startswith(str(workspace))
    backend.stop_session.assert_awaited_once()


# ── start_session ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_session_creates_directories(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    spec = BoxSpec(session_id="sess1", cmd="echo hi")

    info = await backend.start_session(spec)

    session_dir = pathlib.Path(info.backend_session_id)
    assert session_dir.exists()
    assert (session_dir / "root").is_dir()
    assert (session_dir / "workspace").is_dir()
    assert (session_dir / "tmp").is_dir()
    assert (session_dir / "home").is_dir()
    assert (session_dir / "meta.json").exists()

    assert info.backend_name == "nsjail"
    assert info.session_id == "sess1"
    assert info.image == spec.image
    assert info.read_only_rootfs is True


@pytest.mark.anyio
async def test_start_session_with_host_path(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    host_path = str(tmp_base / "rw_host")
    spec = BoxSpec(
        session_id="sess2",
        cmd="ls",
        host_path=host_path,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/project",
    )

    info = await backend.start_session(spec)
    assert info.host_path == host_path
    assert info.host_path_mode == BoxHostMountMode.READ_WRITE
    assert info.mount_path == "/project"


@pytest.mark.anyio
async def test_start_session_creates_missing_rw_host_path(backend, tmp_base):
    """Regression: a read-write host_path that does not yet exist must be
    created by start_session, otherwise nsjail's --bindmount source is missing
    and the command exits 255 with no output (SaaS MCP shared-workspace bug)."""
    tmp_base.mkdir(parents=True, exist_ok=True)
    host_path = tmp_base / "never_created" / "workspace"
    assert not host_path.exists()

    spec = BoxSpec(
        session_id="sess-mkdir",
        cmd="ls",
        host_path=str(host_path),
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/workspace",
    )

    await backend.start_session(spec)
    assert host_path.is_dir()


@pytest.mark.anyio
async def test_start_session_does_not_create_ro_host_path(backend, tmp_base):
    """A missing read-only host_path is a caller error and must NOT be silently
    created — it should surface rather than mount an empty dir."""
    tmp_base.mkdir(parents=True, exist_ok=True)
    host_path = tmp_base / "ro_missing"
    assert not host_path.exists()

    spec = BoxSpec(
        session_id="sess-ro",
        cmd="ls",
        host_path=str(host_path),
        host_path_mode=BoxHostMountMode.READ_ONLY,
        mount_path="/project",
    )

    await backend.start_session(spec)
    assert not host_path.exists()


# ── stop_session ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_stop_session_removes_directory(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    spec = BoxSpec(session_id="sess-rm", cmd="echo")

    info = await backend.start_session(spec)
    session_dir = pathlib.Path(info.backend_session_id)
    assert session_dir.exists()

    await backend.stop_session(info)
    assert not session_dir.exists()


# ── nsjail argument construction ──────────────────────────────────────


def test_build_nsjail_args_basic(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_base / "test_session"
    for d in ("root", "workspace", "tmp", "home"):
        (session_dir / d).mkdir(parents=True)

    spec = BoxSpec(session_id="s1", cmd="echo hello", env={"FOO": "bar"})
    session = BoxSessionInfo(
        session_id="s1",
        backend_name="nsjail",
        backend_session_id=str(session_dir),
        image=spec.image,
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )

    args = backend._build_nsjail_args(session, spec, session_dir)

    assert args[0] == "nsjail"
    assert "--mode" in args
    assert args[args.index("--mode") + 1] == "o"
    assert "--chroot" in args
    assert args[args.index("--chroot") + 1] == str(session_dir / "root")
    assert "--clone_newnet" not in args
    assert "--clone_newuser" not in args
    assert "--clone_newns" not in args
    assert "--disable_clone_newnet" not in args
    assert "--really_quiet" in args

    # Writable mounts should reference session directories.
    rw_binds = [args[i + 1] for i, a in enumerate(args) if a == "--bindmount"]
    workspace_mount = f"{session_dir / 'workspace'}:/workspace"
    assert workspace_mount in rw_binds

    # Custom env should be present.
    env_values = [args[i + 1] for i, a in enumerate(args) if a == "--env"]
    assert "FOO=bar" in env_values

    # Command is the last part after '--'.
    separator_idx = args.index("--")
    assert args[separator_idx + 1] == "/bin/sh"

    # Mount target directories are created under the per-session chroot root.
    assert (session_dir / "root" / "workspace").is_dir()
    assert (session_dir / "root" / "tmp").is_dir()
    assert (session_dir / "root" / "home").is_dir()


def test_build_nsjail_args_binds_essential_dev_nodes(backend, tmp_base):
    """/dev is a fresh empty tmpfs, so essential character devices must be
    bind-mounted in. Regression: without /dev/null, uv's glibc/musl detection
    subprocess fails ("Could not detect either glibc version nor musl libc
    version") and uvx-launched stdio MCP servers die before the initialize
    handshake, surfacing as a misleading "Connection closed / please check URL".
    """
    tmp_base.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_base / "test_dev"
    for d in ("root", "workspace", "tmp", "home"):
        (session_dir / d).mkdir(parents=True)

    spec = BoxSpec(session_id="s-dev", cmd="echo hi")
    session = BoxSessionInfo(
        session_id="s-dev",
        backend_name="nsjail",
        backend_session_id=str(session_dir),
        image=spec.image,
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )

    # Pretend every candidate device node exists on the host.
    with mock.patch("os.path.exists", return_value=True):
        args = backend._build_nsjail_args(session, spec, session_dir)

    # /dev itself is a tmpfs mount.
    mount_specs = [args[i + 1] for i, a in enumerate(args) if a == "--mount"]
    assert "none:/dev:tmpfs:rw" in mount_specs

    # /dev/null (the critical one for uv) must be bind-mounted read-write,
    # ordered AFTER the /dev tmpfs mount so it lands on the fresh tmpfs.
    rw_binds = [args[i + 1] for i, a in enumerate(args) if a == "--bindmount"]
    assert "/dev/null:/dev/null" in rw_binds
    assert "/dev/urandom:/dev/urandom" in rw_binds

    dev_tmpfs_idx = next(
        i
        for i, a in enumerate(args)
        if a == "--mount" and args[i + 1] == "none:/dev:tmpfs:rw"
    )
    dev_null_idx = next(
        i
        for i, a in enumerate(args)
        if a == "--bindmount" and args[i + 1] == "/dev/null:/dev/null"
    )
    assert dev_tmpfs_idx < dev_null_idx


def test_build_nsjail_args_network_on(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_base / "test_session_net"
    for d in ("root", "workspace", "tmp", "home"):
        (session_dir / d).mkdir(parents=True)

    session = BoxSessionInfo(
        session_id="s2",
        backend_name="nsjail",
        backend_session_id=str(session_dir),
        image="host",
        network=BoxNetworkMode.ON,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(
        session_id="s2", cmd="curl http://example.com", network=BoxNetworkMode.ON
    )

    args = backend._build_nsjail_args(session, spec, session_dir)

    assert "--disable_clone_newnet" in args
    assert "--clone_newnet" not in args


def test_build_nsjail_args_host_path_ro(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_base / "test_hp"
    for d in ("root", "workspace", "tmp", "home"):
        (session_dir / d).mkdir(parents=True)

    session = BoxSessionInfo(
        session_id="s3",
        backend_name="nsjail",
        backend_session_id=str(session_dir),
        image="host",
        network=BoxNetworkMode.OFF,
        host_path="/data/project",
        host_path_mode=BoxHostMountMode.READ_ONLY,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(
        session_id="s3",
        cmd="ls",
        host_path="/data/project",
        host_path_mode=BoxHostMountMode.READ_ONLY,
    )

    args = backend._build_nsjail_args(session, spec, session_dir)

    ro_binds = [args[i + 1] for i, a in enumerate(args) if a == "--bindmount_ro"]
    assert "/data/project:/workspace" in ro_binds


def test_build_nsjail_args_uses_custom_mount_path(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_base / "test_custom_mount"
    for d in ("root", "workspace", "tmp", "home"):
        (session_dir / d).mkdir(parents=True)

    session = BoxSessionInfo(
        session_id="s4",
        backend_name="nsjail",
        backend_session_id=str(session_dir),
        image="host",
        network=BoxNetworkMode.OFF,
        host_path="/data/project",
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/project",
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(
        session_id="s4",
        cmd="pwd",
        workdir="/project/src",
        host_path="/data/project",
        host_path_mode=BoxHostMountMode.READ_WRITE,
        mount_path="/project",
    )

    args = backend._build_nsjail_args(session, spec, session_dir)

    rw_binds = [args[i + 1] for i, a in enumerate(args) if a == "--bindmount"]
    assert "/data/project:/project" in rw_binds
    assert args[args.index("--cwd") + 1] == "/project/src"
    assert (session_dir / "root" / "project").is_dir()


def test_build_nsjail_args_extra_mounts_prepare_targets(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_base / "test_extra_mount"
    for d in ("root", "workspace", "tmp", "home"):
        (session_dir / d).mkdir(parents=True)

    session = BoxSessionInfo(
        session_id="s5",
        backend_name="nsjail",
        backend_session_id=str(session_dir),
        image="host",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(
        session_id="s5",
        cmd="ls /workspace/.skills/demo",
        extra_mounts=[
            BoxMountSpec(
                host_path="/data/skills/demo",
                mount_path="/workspace/.skills/demo",
                mode=BoxHostMountMode.READ_WRITE,
            )
        ],
    )

    args = backend._build_nsjail_args(session, spec, session_dir)

    rw_binds = [args[i + 1] for i, a in enumerate(args) if a == "--bindmount"]
    assert "/data/skills/demo:/workspace/.skills/demo" in rw_binds
    assert (session_dir / "root" / "workspace" / ".skills" / "demo").is_dir()


def test_build_resource_limits_cgroup(backend):
    backend._cgroup_v2_available = True
    spec = BoxSpec(session_id="s", cmd="x", cpus=2.0, memory_mb=1024, pids_limit=256)

    args = backend._build_resource_limits(spec)

    # Bug regression: cgroup v2 mode MUST opt in explicitly, otherwise nsjail
    # falls back to the v1 layout and aborts on a v2-only host.
    assert "--use_cgroupv2" in args
    assert "--cgroup_mem_max" in args
    mem_idx = args.index("--cgroup_mem_max")
    assert args[mem_idx + 1] == str(1024 * 1024 * 1024)
    swap_idx = args.index("--cgroup_mem_swap_max")
    assert args[swap_idx + 1] == "0"

    pids_idx = args.index("--cgroup_pids_max")
    assert args[pids_idx + 1] == "256"

    cpu_idx = args.index("--cgroup_cpu_ms_per_sec")
    assert args[cpu_idx + 1] == "2000"

    # Virtual address space must be raised to the hard limit so node/V8 WASM
    # (and other runtimes reserving large vaddr) can boot; physical memory is
    # still bounded by --cgroup_mem_max above.
    assert "--rlimit_as" in args
    ras_idx = args.index("--rlimit_as")
    assert args[ras_idx + 1] == "hard"


def test_build_resource_limits_rlimit_fallback(backend):
    backend._cgroup_v2_available = False
    spec = BoxSpec(session_id="s", cmd="x", memory_mb=512, pids_limit=128)

    args = backend._build_resource_limits(spec)

    # Bug regression: --rlimit_as must be set to "hard" (the current hard
    # limit), NOT a small value. A small RLIMIT_AS caps *virtual* address space,
    # which uv/node/Rust/JVM reserve in huge amounts, so it aborts them
    # instantly ("memory allocation failed" / node WASM "Cannot allocate Wasm
    # memory") and silently broke every uvx/npx stdio MCP server. "hard" leaves
    # virtual address space uncapped; resident memory is bounded by cgroups
    # (cgroup branch) or the container mem_limit (fallback branch).
    assert "--rlimit_as" in args
    ras_idx = args.index("--rlimit_as")
    assert args[ras_idx + 1] == "hard"

    nproc_idx = args.index("--rlimit_nproc")
    assert args[nproc_idx + 1] == "128"

    # Safe rlimits still apply.
    assert "--rlimit_fsize" in args
    assert "--rlimit_nofile" in args

    # cgroup flags should NOT be present.
    assert "--use_cgroupv2" not in args
    assert "--cgroup_mem_max" not in args


# ── exec ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure", [None, OSError("launch failed"), asyncio.CancelledError()]
)
async def test_large_exec_script_is_preserved_and_cleaned(backend, failure):
    from langbot_plugin.box.backend import _CommandResult

    command = "printf '%s' '" + "附件" * 2000 + "'"
    spec = BoxSpec(session_id="large", cmd=command)
    info = await backend.start_session(spec)
    script_dir = pathlib.Path(info.backend_session_id) / "tmp"

    async def run(args, timeout_sec):
        scripts = list(script_dir.glob(".langbot-exec-*.sh"))
        assert len(scripts) == 1
        assert scripts[0].read_text(encoding="utf-8").endswith(command)
        assert args[-1] == f". /tmp/{scripts[0].name}"
        assert max(len(arg.encode("utf-8")) for arg in args) < 8192
        if failure is not None:
            raise failure
        return _CommandResult(return_code=0, stdout="ok", stderr="")

    with mock.patch.object(backend, "_run_nsjail", side_effect=run):
        if failure is None:
            assert (await backend.exec(info, spec)).ok
        else:
            with pytest.raises(type(failure)):
                await backend.exec(info, spec)
    assert not list(script_dir.glob(".langbot-exec-*.sh"))


@pytest.mark.anyio
async def test_exec_success(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    spec = BoxSpec(session_id="exec1", cmd="echo hello")
    info = await backend.start_session(spec)

    with mock.patch.object(backend, "_run_nsjail") as mock_run:
        from langbot_plugin.box.backend import _CommandResult

        mock_run.return_value = _CommandResult(
            return_code=0, stdout="hello\n", stderr="", timed_out=False
        )

        result = await backend.exec(info, spec)

    assert result.status == BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.backend_name == "nsjail"


@pytest.mark.anyio
async def test_exec_timeout(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)
    spec = BoxSpec(session_id="exec2", cmd="sleep 100", timeout_sec=1)
    info = await backend.start_session(spec)

    with mock.patch.object(backend, "_run_nsjail") as mock_run:
        from langbot_plugin.box.backend import _CommandResult

        mock_run.return_value = _CommandResult(
            return_code=-1, stdout="", stderr="", timed_out=True
        )

        result = await backend.exec(info, spec)

    assert result.status == BoxExecutionStatus.TIMED_OUT
    assert result.exit_code is None


@pytest.mark.anyio
@pytest.mark.parametrize("stop_reason", ["timeout", "cancel"])
async def test_run_nsjail_termination_allows_cleanup(
    backend,
    monkeypatch,
    stop_reason,
):
    class EmptyStream:
        async def read(self, _size):
            return b""

    class HangingProcess:
        def __init__(self):
            self.returncode = None
            self.stdout = EmptyStream()
            self.stderr = EmptyStream()
            self.wait_started = asyncio.Event()
            self.exit_requested = asyncio.Event()
            self.terminated = False
            self.killed = False

        async def wait(self):
            self.wait_started.set()
            await self.exit_requested.wait()
            self.returncode = -15
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.exit_requested.set()

        def kill(self):
            self.killed = True
            self.exit_requested.set()

    process = HangingProcess()

    async def create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(
        nsjail_backend_module.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )
    task = asyncio.create_task(
        backend._run_nsjail(
            ["nsjail", "--help"],
            timeout_sec=0.01 if stop_reason == "timeout" else 60,
        )
    )
    await process.wait_started.wait()
    if stop_reason == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert result.timed_out is True
        assert result.return_code == -1
    assert process.terminated is True
    assert process.killed is False
    assert process.returncode == -15


# ── cgroup detection ──────────────────────────────────────────────────


def test_detect_cgroup_v2_no_mount():
    with mock.patch.object(pathlib.Path, "exists", return_value=False):
        assert NsjailBackend._detect_cgroup_v2() is False


def test_detect_cgroup_v2_subtree_writable():
    """When writing to cgroup.subtree_control succeeds, report True.

    This is the authoritative probe: it mirrors exactly what nsjail does with
    --use_cgroupv2 (enable a controller on the root's subtree_control so the
    child cgroup can use it). A plain mkdir probe is insufficient because it
    succeeds even in a private cgroup namespace where the subtree_control write
    then fails with EBUSY.
    """

    def fake_exists(self):
        path = str(self).replace("\\", "/")
        return path in (
            "/sys/fs/cgroup",
            "/sys/fs/cgroup/cgroup.controllers",
            "/sys/fs/cgroup/cgroup.subtree_control",
        )

    def fake_read_text(self, *a, **k):
        path = str(self)
        if path.endswith("cgroup.controllers"):
            return "cpuset cpu io memory hugetlb pids"
        if path.endswith("cgroup.subtree_control"):
            return ""  # nothing delegated yet -> probe will enable then disable
        raise FileNotFoundError(path)

    writes: list[str] = []

    def fake_write_text(self, data, *a, **k):
        writes.append(data)
        return len(data)

    with (
        mock.patch.object(pathlib.Path, "exists", fake_exists),
        mock.patch.object(pathlib.Path, "read_text", fake_read_text),
        mock.patch.object(pathlib.Path, "write_text", fake_write_text),
    ):
        assert NsjailBackend._detect_cgroup_v2() is True
    # Probe must validate every limit controller and leave host config untouched.
    assert writes == [
        "+memory",
        "-memory",
        "+pids",
        "-pids",
        "+cpu",
        "-cpu",
    ]


def test_detect_cgroup_v2_rejects_partial_controller_delegation():
    def fake_exists(self):
        return str(self) in (
            "/sys/fs/cgroup",
            "/sys/fs/cgroup/cgroup.controllers",
            "/sys/fs/cgroup/cgroup.subtree_control",
        )

    def fake_read_text(self, *a, **k):
        if str(self).endswith("cgroup.controllers"):
            return "cpu memory"
        return ""

    with (
        mock.patch.object(pathlib.Path, "exists", fake_exists),
        mock.patch.object(pathlib.Path, "read_text", fake_read_text),
    ):
        assert NsjailBackend._detect_cgroup_v2() is False


@pytest.mark.skipif(
    os.name == "nt",
    reason="NsJail is Linux-only and Windows may not permit symlinks",
)
def test_readonly_system_symlink_is_recreated_without_bind_mount(
    backend, tmp_path, monkeypatch
):
    host_root = tmp_path / "host"
    (host_root / "usr" / "bin").mkdir(parents=True)
    host_link = host_root / "bin"
    host_link.symlink_to("usr/bin")
    monkeypatch.setattr(
        nsjail_backend_module, "_READONLY_SYSTEM_MOUNTS", [str(host_link)]
    )
    monkeypatch.setattr(nsjail_backend_module, "_READONLY_ETC_ENTRIES", [])

    session = BoxSessionInfo(
        session_id="symlink",
        backend_name="nsjail",
        backend_session_id=str(tmp_path / "session"),
        image="python:3.12",
        network=BoxNetworkMode.OFF,
        created_at="2024-01-01T00:00:00+00:00",
        last_used_at="2024-01-01T00:00:00+00:00",
    )
    spec = BoxSpec(session_id="symlink", cmd="true")
    jail_root = tmp_path / "jail"
    backend._ensure_chroot_mount_targets(jail_root, session, spec)

    jail_link = jail_root / str(host_link).lstrip("/")
    assert jail_link.is_symlink()
    assert jail_link.readlink() == host_link.readlink()
    assert backend._build_readonly_mounts(BoxNetworkMode.OFF) == []


def test_detect_cgroup_v2_private_cgroupns_ebusy_returns_false():
    """A private cgroup namespace (Docker/k8s default) lets mkdir succeed but
    rejects the subtree_control write with EBUSY (no-internal-process rule).
    The probe MUST catch this and report False so the backend uses the rlimit
    fallback instead of selecting a cgroup path that aborts nsjail (exit 255).
    """

    def fake_exists(self):
        path = str(self)
        return path in (
            "/sys/fs/cgroup",
            "/sys/fs/cgroup/cgroup.controllers",
            "/sys/fs/cgroup/cgroup.subtree_control",
        )

    def fake_read_text(self, *a, **k):
        path = str(self)
        if path.endswith("cgroup.controllers"):
            return "cpu memory pids"
        if path.endswith("cgroup.subtree_control"):
            return ""
        raise FileNotFoundError(path)

    def fake_write_text(self, data, *a, **k):
        raise OSError(16, "Device or resource busy")

    with (
        mock.patch.object(pathlib.Path, "exists", fake_exists),
        mock.patch.object(pathlib.Path, "read_text", fake_read_text),
        mock.patch.object(pathlib.Path, "write_text", fake_write_text),
    ):
        assert NsjailBackend._detect_cgroup_v2() is False


def test_detect_cgroup_v2_no_subtree_control_returns_false():
    """A read-only /sys/fs/cgroup with no subtree_control file reports False."""

    def fake_exists(self):
        path = str(self)
        return path in (
            "/sys/fs/cgroup",
            "/sys/fs/cgroup/cgroup.controllers",
        )

    with mock.patch.object(pathlib.Path, "exists", fake_exists):
        assert NsjailBackend._detect_cgroup_v2() is False


# ── cleanup_orphaned_containers ───────────────────────────────────────


@pytest.mark.anyio
async def test_cleanup_orphaned_removes_old_sessions(backend, tmp_base):
    tmp_base.mkdir(parents=True, exist_ok=True)

    # Create a dir from a different instance.
    old_dir = tmp_base / "oldinst_sess1_abc"
    old_dir.mkdir()
    (old_dir / "workspace").mkdir()

    # Create a dir from current instance.
    current_dir = tmp_base / "test123_sess2_def"
    current_dir.mkdir()
    (current_dir / "workspace").mkdir()
    (current_dir / "meta.json").write_text('{"instance_id":"test123"}')
    prefix_collision = tmp_base / "test123_other_sess3_abc"
    prefix_collision.mkdir()
    (prefix_collision / "meta.json").write_text('{"instance_id":"test123_other"}')
    unlabeled = tmp_base / "test123_legacy"
    unlabeled.mkdir()

    with mock.patch.object(
        backend,
        "_kill_orphaned_session_processes_sync",
    ) as kill_processes:
        await backend.cleanup_orphaned_containers("test123")

    kill_processes.assert_called_once_with("test123")
    assert old_dir.exists()
    assert not current_dir.exists()
    assert prefix_collision.exists()
    assert unlabeled.exists()


@pytest.mark.skipif(os.name == "nt", reason="NsJail process cleanup is Linux-only")
def test_kill_orphaned_processes_scans_proc_once(
    backend,
    tmp_base,
    tmp_path,
):
    proc_dir = tmp_path / "proc"
    old_pid = proc_dir / "101"
    current_pid = proc_dir / "102"
    unrelated_pid = proc_dir / "103"
    for pid_dir in (old_pid, current_pid, unrelated_pid):
        pid_dir.mkdir(parents=True)
    (old_pid / "cmdline").write_bytes(
        (f"nsjail\0--chroot\0{tmp_base}/oldinst_sess1_abc/root\0").encode()
    )
    (current_pid / "cmdline").write_bytes(
        (f"nsjail\0--chroot\0{tmp_base}/test123_sess2_def/root\0").encode()
    )
    (unrelated_pid / "cmdline").write_bytes(b"python\0worker.py\0")
    current_dir = tmp_base / "test123_sess2_def"
    current_dir.mkdir(parents=True)
    (current_dir / "meta.json").write_text('{"instance_id":"test123"}')

    with mock.patch("os.kill") as kill:
        backend._kill_orphaned_session_processes_sync(
            "test123",
            proc_dir=proc_dir,
        )

    kill.assert_called_once_with(102, 9)


# ── output clipping ──────────────────────────────────────────────────


def test_clip_captured_bytes_within_limit():
    data = b"hello world"
    result = NsjailBackend._clip_captured_bytes(data, len(data))
    assert result == "hello world"


def test_clip_captured_bytes_exceeds_limit():
    data = b"hello"
    result = NsjailBackend._clip_captured_bytes(data, 2_000_000, limit=1_000_000)
    assert "clipped" in result
    assert "1000000" in result


@pytest.mark.parametrize(
    "parent", ["../other", "/absolute", ".", "..", "a/b", "a\\b", True]
)
def test_cgroup_v1_parent_rejects_invalid_paths(backend, parent):
    with pytest.raises(ValueError, match="single directory"):
        backend.configure({"cgroup_v1_parent": parent})


def test_cgroup_v1_limits_are_per_jail_instead_of_per_host_uid(backend):
    backend.configure({"cgroup_v1_parent": "langbot-test"})
    backend._cgroup_v1_available = True
    spec = BoxSpec(session_id="v1", cmd="true", cpus=1.5, memory_mb=256, pids_limit=16)
    args = backend._build_resource_limits(spec)
    assert "--use_cgroupv2" not in args
    for flag, value in {
        "--cgroup_mem_parent": "langbot-test",
        "--cgroup_pids_parent": "langbot-test",
        "--cgroup_cpu_parent": "langbot-test",
        "--cgroup_mem_max": str(256 * 1024 * 1024),
        "--cgroup_mem_memsw_max": str(256 * 1024 * 1024),
        "--cgroup_pids_max": "16",
        "--cgroup_cpu_ms_per_sec": "1500",
        "--rlimit_nproc": "hard",
    }.items():
        assert args[args.index(flag) + 1] == value


@pytest.mark.anyio
async def test_explicit_cgroup_v1_delegation_never_silently_falls_back(backend):
    backend.configure({"cgroup_v1_parent": "missing"})
    process = mock.AsyncMock()
    process.returncode = 0
    with (
        mock.patch("shutil.which", return_value="/usr/bin/nsjail"),
        mock.patch("asyncio.create_subprocess_exec", return_value=process),
        mock.patch.object(backend, "_detect_cgroup_v2", return_value=False),
        mock.patch.object(
            backend, "_probe_cgroup_v1", side_effect=OSError("not delegated")
        ),
    ):
        assert await backend.is_available() is False
        assert backend._cgroup_v1_available is False
        with pytest.raises(BoxError, match="delegation is unavailable"):
            backend._build_resource_limits(BoxSpec(session_id="must-not-downgrade"))
        with pytest.raises(BoxError, match="delegation is unavailable"):
            await backend.initialize()


@pytest.mark.anyio
async def test_refresh_does_not_remove_working_cgroup_limits_while_probe_runs(backend):
    backend.configure({"cgroup_v1_parent": "delegated"})
    backend._cgroup_v1_available = True
    entered, release = asyncio.Event(), asyncio.Event()
    process = mock.AsyncMock()
    process.returncode = 0

    async def offload(function, *args, **kwargs):
        if function == backend._detect_cgroup_v2:
            return False
        if function == backend._probe_cgroup_v1:
            entered.set()
            await release.wait()
            return None
        return function(*args, **kwargs)

    with (
        mock.patch("shutil.which", return_value="/usr/bin/nsjail"),
        mock.patch("asyncio.create_subprocess_exec", return_value=process),
        mock.patch("asyncio.to_thread", side_effect=offload),
    ):
        probe = asyncio.create_task(backend.is_available())
        await entered.wait()
        args = backend._build_resource_limits(
            BoxSpec(session_id="during-refresh", pids_limit=16)
        )
        assert args[args.index("--cgroup_pids_max") + 1] == "16"
        assert args[args.index("--rlimit_nproc") + 1] == "hard"
        release.set()
        assert await probe is True
