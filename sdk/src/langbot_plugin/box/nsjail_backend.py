from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import pathlib
import shlex
import shutil
import signal
import tempfile
import uuid
from typing import Any

from langbot_plugin.runtime import bounded_executor

from .backend import BaseSandboxBackend, _CommandResult
from .models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)
from .security import validate_sandbox_security

_LOGGER = logging.getLogger(__name__)

# System directories to mount read-only inside the sandbox.
# Only well-known paths needed for running Python/Node/shell commands.
_READONLY_SYSTEM_MOUNTS: list[str] = [
    "/usr",
    "/lib",
    "/lib64",
    "/bin",
    "/sbin",
]

# Specific /etc entries required for dynamic linking and TLS.
_READONLY_ETC_ENTRIES: list[str] = [
    "/etc/alternatives",
    "/etc/ld.so.cache",
    "/etc/ld.so.conf",
    "/etc/ld.so.conf.d",
    "/etc/ssl/certs",
    "/etc/localtime",
    "/etc/resolv.conf",  # needed when network=ON
]

# Essential character devices bind-mounted into the sandbox's /dev.
# /dev is a fresh empty tmpfs (see _build_args), so these nodes do not exist
# unless we bind them in from the host. Tooling that shells out for probes
# relies on them — notably `uv`/`uvx` redirects its glibc/musl detection
# subprocess to /dev/null; without it uv fails with "Could not detect either
# glibc version nor musl libc version" and the process exits before it can do
# anything (e.g. an stdio MCP server dies before the initialize handshake,
# surfacing as a misleading "Connection closed / please check URL").
_DEV_NODES: list[str] = [
    "/dev/null",
    "/dev/zero",
    "/dev/full",
    "/dev/random",
    "/dev/urandom",
    "/dev/tty",
]

_DEFAULT_BASE_DIR = "/tmp/langbot-box-nsjail"


class NsjailBackend(BaseSandboxBackend):
    """Lightweight sandbox backend using nsjail.

    Each ``exec`` invocation spawns an independent nsjail process.  Session
    state (workspace files) persists via a shared host directory that is
    bind-mounted into every invocation.
    """

    execution_scoped_mounts = True
    name = "nsjail"

    def __init__(
        self,
        logger: logging.Logger,
        nsjail_bin: str = "nsjail",
        base_dir: str = _DEFAULT_BASE_DIR,
    ):
        super().__init__(logger)
        self._nsjail_bin = nsjail_bin
        self._base_dir = pathlib.Path(base_dir)
        self._cgroup_v2_available: bool = False

    # ── lifecycle ─────────────────────────────────────────────────────

    async def is_available(self) -> bool:
        if shutil.which(self._nsjail_bin) is None:
            self.logger.info("nsjail binary not found in PATH")
            return False

        # Quick sanity check – nsjail --help exits 0.
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                self._nsjail_bin,
                "--help",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            if proc.returncode != 0:
                self.logger.info("nsjail --help returned non-zero")
                return False
        except asyncio.CancelledError:
            if proc is not None:
                await self._terminate_process(proc)
            raise
        except Exception as exc:
            if proc is not None:
                await self._terminate_process(proc)
            self.logger.info(f"nsjail probe failed: {exc}")
            return False

        self._cgroup_v2_available = await asyncio.to_thread(self._detect_cgroup_v2)
        if not self._cgroup_v2_available:
            self.logger.warning(
                "nsjail cgroup v2 limits unavailable (private cgroup namespace "
                "or read-only /sys/fs/cgroup); falling back to rlimit-based "
                "limits WITHOUT a hard memory cap. RLIMIT_AS is intentionally "
                "not used because it kills uv/node/etc. To enforce a memory "
                "cap, run the Box container in the host cgroup namespace "
                "(--cgroupns=host / compose `cgroup: host`) or set a "
                "container-level memory limit."
            )

        await asyncio.to_thread(
            self._base_dir.mkdir,
            parents=True,
            exist_ok=True,
        )
        return True

    async def get_readiness(
        self,
        *,
        workspace_path: str | None = None,
        strict: bool = False,
    ) -> dict:
        """Probe the isolation guarantees required by managed nsjail mode."""

        available = await self.is_available()
        readiness: dict[str, Any] = {
            "available": available,
            "cgroup_v2": self._cgroup_v2_available if available else False,
            "namespace_isolation": None,
            "mount_isolation": None,
            "network_isolation": None,
            # nsjail itself does not provide byte/inode accounting for bind
            # mounts, generic read-only mount sources, or its private
            # root/tmp/home. A future operator-owned project/subvolume quota
            # provider may override these only after it can attest both the
            # workspace and mounted backing filesystems.
            # Runtime/Core payloads are intentionally not consulted.
            "hard_workspace_quota": False,
            "hard_read_only_mount_quota": False,
            "bounded_ephemeral_storage": False,
            "inode_quota": False,
        }
        if not strict:
            return readiness

        if not available:
            readiness.update(
                {
                    "namespace_isolation": False,
                    "mount_isolation": False,
                    "network_isolation": False,
                    "hard_workspace_quota": False,
                    "hard_read_only_mount_quota": False,
                    "bounded_ephemeral_storage": False,
                    "inode_quota": False,
                }
            )
            return readiness

        if not workspace_path:
            readiness.update(
                {
                    "namespace_isolation": False,
                    "mount_isolation": False,
                    "network_isolation": False,
                    "hard_workspace_quota": False,
                    "hard_read_only_mount_quota": False,
                    "bounded_ephemeral_storage": False,
                    "inode_quota": False,
                    "error": "managed nsjail readiness requires a durable workspace path",
                }
            )
            return readiness

        try:
            probe = await self._probe_isolation_readiness(workspace_path)
        except Exception as exc:
            self.logger.warning(f"nsjail strict readiness probe failed: {exc}")
            probe = {
                "namespace_isolation": False,
                "mount_isolation": False,
                "network_isolation": False,
                "hard_workspace_quota": False,
                "hard_read_only_mount_quota": False,
                "bounded_ephemeral_storage": False,
                "inode_quota": False,
                "error": str(exc),
            }
        readiness.update(probe)
        return readiness

    async def _probe_isolation_readiness(self, workspace_path: str) -> dict:
        """Run a disposable offline jail and verify its namespace and bind mount."""

        def prepare_probe_path() -> pathlib.Path:
            workspace_root = pathlib.Path(workspace_path).resolve()
            if not workspace_root.is_dir():
                raise RuntimeError("managed sandbox workspace path is not a directory")
            if not os.access(workspace_root, os.R_OK | os.W_OK | os.X_OK):
                raise RuntimeError("managed sandbox workspace path is not writable")
            return pathlib.Path(
                tempfile.mkdtemp(
                    prefix=".box-readiness-",
                    dir=str(workspace_root),
                )
            )

        probe_path = await bounded_executor.run_blocking_atomic(prepare_probe_path)
        marker_name = ".mounted"
        marker_path = probe_path / marker_name
        session_info: BoxSessionInfo | None = None
        try:
            spec = BoxSpec(
                session_id=f"readiness-{uuid.uuid4().hex}",
                cmd=(
                    f"printf readiness > /workspace/{marker_name} && "
                    "readlink /proc/self/ns/net"
                ),
                network=BoxNetworkMode.OFF,
                host_path=str(probe_path),
                host_path_mode=BoxHostMountMode.READ_WRITE,
                mount_path="/workspace",
                workdir="/workspace",
                persistent=False,
                read_only_rootfs=True,
            )
            session_info = await self.start_session(spec)
            result = await self.exec(session_info, spec)
            sandbox_net_namespace_lines = (result.stdout or "").strip().splitlines()
            sandbox_net_namespace = (
                sandbox_net_namespace_lines[-1] if sandbox_net_namespace_lines else ""
            )
            try:
                host_net_namespace = os.readlink("/proc/self/ns/net")
            except OSError:
                host_net_namespace = ""

            mount_isolation = result.ok and await asyncio.to_thread(
                lambda: marker_path.is_file() and marker_path.read_text() == "readiness"
            )
            network_isolation = bool(
                result.ok
                and host_net_namespace
                and sandbox_net_namespace
                and sandbox_net_namespace != host_net_namespace
            )
            return {
                "namespace_isolation": result.ok,
                "mount_isolation": mount_isolation,
                "network_isolation": network_isolation,
            }
        finally:
            if session_info is not None:
                await self.stop_session(session_info)
            await bounded_executor.run_blocking_cleanup(
                shutil.rmtree,
                probe_path,
                True,
            )

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        validate_sandbox_security(spec)

        now = dt.datetime.now(dt.timezone.utc)
        session_dir_name = (
            f"{self.instance_id}_{spec.session_id}_{uuid.uuid4().hex[:8]}"
        )
        session_dir = self._base_dir / session_dir_name

        # Per-session writable directories.
        root_dir = session_dir / "root"
        workspace_dir = session_dir / "workspace"
        tmp_dir = session_dir / "tmp"
        home_dir = session_dir / "home"

        meta = {
            "session_id": spec.session_id,
            "instance_id": self.instance_id,
            "host_path": spec.host_path,
            "host_path_mode": spec.host_path_mode.value if spec.host_path else None,
            "mount_path": spec.mount_path,
            "network": spec.network.value,
            "cpus": spec.cpus,
            "memory_mb": spec.memory_mb,
            "pids_limit": spec.pids_limit,
            "created_at": now.isoformat(),
        }

        def prepare_session_directory() -> None:
            for directory in (root_dir, workspace_dir, tmp_dir, home_dir):
                directory.mkdir(parents=True, exist_ok=True)

            # nsjail requires writable bind-mount sources to exist before
            # launch. Missing read-only sources remain caller errors.
            if (
                spec.host_path is not None
                and spec.host_path_mode == BoxHostMountMode.READ_WRITE
            ):
                os.makedirs(spec.host_path, exist_ok=True)
            (session_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        try:
            await bounded_executor.run_blocking_atomic(prepare_session_directory)
        except BaseException:
            await bounded_executor.run_blocking_cleanup(
                shutil.rmtree,
                session_dir,
                True,
            )
            raise

        self.logger.info(
            f"LangBot Box backend start_session: backend=nsjail "
            f"session_id={spec.session_id} session_dir={session_dir} "
            f"network={spec.network.value} "
            f"host_path={spec.host_path} host_path_mode={spec.host_path_mode.value} mount_path={spec.mount_path} "
            f"cpus={spec.cpus} memory_mb={spec.memory_mb} pids_limit={spec.pids_limit} "
            f"workspace_quota_mb={spec.workspace_quota_mb}"
        )

        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=str(session_dir),
            # Keep the requested logical image in metadata so runtime session
            # reuse sees later specs as compatible. nsjail still executes
            # against host-mounted system paths rather than a container image.
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            mount_path=spec.mount_path,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
            workspace_quota_mb=spec.workspace_quota_mb,
            persistent=spec.persistent,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        start = dt.datetime.now(dt.timezone.utc)
        session_dir = pathlib.Path(session.backend_session_id)

        args = await bounded_executor.run_blocking_atomic(
            self._build_nsjail_args,
            session,
            spec,
            session_dir,
        )

        cmd_preview = spec.cmd.strip()
        if len(cmd_preview) > 400:
            cmd_preview = f"{cmd_preview[:397]}..."
        self.logger.info(
            f"LangBot Box backend exec: backend=nsjail "
            f"session_id={session.session_id} session_dir={session_dir} "
            f"workdir={spec.workdir} timeout_sec={spec.timeout_sec} "
            f"env_keys={sorted(spec.env.keys())} cmd={cmd_preview}"
        )

        script_path = None
        try:
            # Attachment manifests and generated code can exceed Linux's
            # per-argument limit. Source a file without consuming command stdin.
            if len(args[-1].encode("utf-8")) > 8192:
                script_path = (
                    session_dir / "tmp" / f".langbot-exec-{uuid.uuid4().hex}.sh"
                )
                await bounded_executor.run_blocking_atomic(
                    self._write_exec_script, script_path, args[-1]
                )
                args[-1] = f". {shlex.quote('/tmp/' + script_path.name)}"
            result = await self._run_nsjail(args, timeout_sec=spec.timeout_sec)
        finally:
            if script_path is not None:
                await bounded_executor.run_blocking_cleanup(
                    script_path.unlink, missing_ok=True
                )
        duration_ms = int(
            (dt.datetime.now(dt.timezone.utc) - start).total_seconds() * 1000
        )

        if result.timed_out:
            return BoxExecutionResult(
                session_id=session.session_id,
                backend_name=self.name,
                status=BoxExecutionStatus.TIMED_OUT,
                exit_code=None,
                stdout=result.stdout,
                stderr=result.stderr
                or f"Command timed out after {spec.timeout_sec} seconds.",
                duration_ms=duration_ms,
            )

        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _write_exec_script(path: pathlib.Path, command: str) -> None:
        with path.open("x", encoding="utf-8") as script:
            script.write(command)

    async def stop_session(self, session: BoxSessionInfo):
        session_dir = pathlib.Path(session.backend_session_id)
        self.logger.info(
            f"LangBot Box backend stop_session: backend=nsjail "
            f"session_id={session.session_id} session_dir={session_dir}"
        )

        # Kill any lingering nsjail processes whose cwd is inside session_dir.
        await self._kill_session_processes(session_dir)

        try:
            await bounded_executor.run_blocking_cleanup(
                lambda: shutil.rmtree(session_dir) if session_dir.exists() else None
            )
        except Exception as exc:
            self.logger.warning(
                f"Failed to remove nsjail session dir {session_dir}: {exc}"
            )

    async def start_managed_process(
        self, session: BoxSessionInfo, spec
    ) -> asyncio.subprocess.Process:
        session_dir = pathlib.Path(session.backend_session_id)

        # Build a BoxSpec-like object so we can reuse _build_nsjail_args.
        # ManagedProcessSpec has command/args/cwd/env but not the full BoxSpec.
        inner_cmd = " ".join(
            [shlex.quote(spec.command), *[shlex.quote(a) for a in spec.args]]
        )
        pseudo_spec = BoxSpec(
            cmd=inner_cmd,
            workdir=spec.cwd,
            timeout_sec=86400,  # not used here
            network=session.network,
            session_id=session.session_id,
            env=spec.env,
            host_path=session.host_path,
            host_path_mode=session.host_path_mode,
            mount_path=session.mount_path,
            cpus=session.cpus,
            # Allow per-process memory override: if the ManagedProcessSpec
            # sets a memory_mb > 0 it wins; otherwise fall back to the session
            # default.  This lets node/npx processes request more RAM than the
            # shared session default without requiring a separate session.
            memory_mb=spec.memory_mb if spec.memory_mb > 0 else session.memory_mb,
            pids_limit=session.pids_limit,
            read_only_rootfs=session.read_only_rootfs,
        )

        args = await bounded_executor.run_blocking_atomic(
            self._build_nsjail_args,
            session,
            pseudo_spec,
            session_dir,
        )

        self.logger.info(
            f"LangBot Box backend start_managed_process: backend=nsjail "
            f"session_id={session.session_id} session_dir={session_dir} "
            f"cwd={spec.cwd} env_keys={sorted(spec.env.keys())} "
            f"command={spec.command} args={spec.args}"
        )

        return await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def cleanup_orphaned_containers(self, current_instance_id: str = ""):
        await bounded_executor.run_blocking_cleanup(
            self._cleanup_orphaned_sessions_sync,
            current_instance_id,
        )

    def _cleanup_orphaned_sessions_sync(
        self,
        current_instance_id: str,
    ) -> None:
        """Scan processes once and stream stale directory removal.

        A crashed Runtime can leave many session directories. Scanning all of
        /proc once per directory turns startup into O(sessions * processes)
        work and materializes every directory in memory. Keep both dimensions
        linear instead.
        """

        if not current_instance_id or not self._base_dir.exists():
            return
        self._kill_orphaned_session_processes_sync(current_instance_id)
        current_prefix = f"{current_instance_id}_"
        for entry in self._base_dir.iterdir():
            try:
                if not entry.is_dir():
                    continue
                if not entry.name.startswith(
                    current_prefix
                ) or not self._session_owned_by(entry, current_instance_id):
                    self.logger.debug(
                        "Skipping nsjail session dir owned by another instance: %s",
                        entry,
                    )
                    continue
            except OSError as exc:
                self.logger.warning(
                    f"Failed to inspect nsjail session dir {entry}: {exc}"
                )
                continue
            self.logger.info(f"Cleaning up orphaned nsjail session dir: {entry}")
            try:
                shutil.rmtree(entry)
            except Exception as exc:
                self.logger.warning(
                    f"Failed to clean up orphaned nsjail dir {entry}: {exc}"
                )

    # ── nsjail argument construction ──────────────────────────────────

    def _session_owned_by(self, session_dir: pathlib.Path, instance_id: str) -> bool:
        try:
            metadata = json.loads((session_dir / "meta.json").read_text())
            return (
                isinstance(metadata, dict)
                and metadata.get("instance_id") == instance_id
            )
        except (OSError, ValueError):
            return False

    def _build_nsjail_args(
        self,
        session: BoxSessionInfo,
        spec: BoxSpec,
        session_dir: pathlib.Path,
    ) -> list[str]:
        args: list[str] = [self._nsjail_bin]

        # Mode: one-shot execution.
        args.extend(["--mode", "o"])

        # nsjail enables the relevant clone namespaces by default. Some
        # versions do not expose positive --clone_new* flags, only disable
        # flags, so rely on defaults for broad compatibility.

        # Use a per-session chroot root so nsjail can create mount targets
        # without needing write access to the host root.
        root_dir = session_dir / "root"
        root_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_chroot_mount_targets(root_dir, session, spec)
        args.extend(["--chroot", str(root_dir)])

        # Network namespace.
        if spec.network != BoxNetworkMode.OFF:
            args.append("--disable_clone_newnet")

        # Read-only system mounts.
        args.extend(self._build_readonly_mounts(spec.network))

        # Writable per-session mounts.
        args.extend(self._build_writable_mounts(session, spec, session_dir))

        # Isolated /proc and minimal /dev.
        args.extend(["--mount", "none:/proc:proc:rw"])
        args.extend(["--mount", "none:/dev:tmpfs:rw"])

        # /dev is a fresh empty tmpfs, so bind in the essential character
        # devices. Without /dev/null in particular, uv's glibc/musl detection
        # subprocess fails and any uvx-launched process (e.g. stdio MCP servers)
        # exits before doing useful work. Mounted read-write so writes to
        # /dev/null behave normally.
        for dev in _DEV_NODES:
            if os.path.exists(dev):
                args.extend(["--bindmount", f"{dev}:{dev}"])

        # Working directory.
        args.extend(["--cwd", spec.workdir])

        # Environment variables.
        args.extend(["--env", "PYTHONUNBUFFERED=1"])
        args.extend(["--env", "HOME=/home"])
        args.extend(
            [
                "--env",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            ]
        )
        for key, value in spec.env.items():
            args.extend(["--env", f"{key}={value}"])

        # Resource limits.
        args.extend(self._build_resource_limits(spec))

        # Suppress nsjail's own log output.
        args.append("--really_quiet")

        # The actual command.
        quoted_workdir = shlex.quote(spec.workdir)
        user_cmd = f"mkdir -p {quoted_workdir} && cd {quoted_workdir} && {spec.cmd}"
        args.extend(["--", "/bin/sh", "-lc", user_cmd])

        return args

    def _build_readonly_mounts(self, network: BoxNetworkMode) -> list[str]:
        args: list[str] = []

        for path in _READONLY_SYSTEM_MOUNTS:
            if os.path.exists(path) and not os.path.islink(path):
                args.extend(["--bindmount_ro", f"{path}:{path}"])

        for path in _READONLY_ETC_ENTRIES:
            # /etc/resolv.conf is only needed when network is ON.
            if path == "/etc/resolv.conf" and network == BoxNetworkMode.OFF:
                continue
            if os.path.exists(path) and not os.path.islink(path):
                args.extend(["--bindmount_ro", f"{path}:{path}"])

        return args

    def _build_writable_mounts(
        self,
        session: BoxSessionInfo,
        spec: BoxSpec,
        session_dir: pathlib.Path,
    ) -> list[str]:
        args: list[str] = []

        # Workspace mount.
        if spec.host_path is not None and spec.host_path_mode != BoxHostMountMode.NONE:
            if spec.host_path_mode == BoxHostMountMode.READ_ONLY:
                args.extend(["--bindmount_ro", f"{spec.host_path}:{spec.mount_path}"])
            else:
                args.extend(["--bindmount", f"{spec.host_path}:{spec.mount_path}"])
        else:
            workspace_dir = session_dir / "workspace"
            args.extend(["--bindmount", f"{workspace_dir}:{spec.mount_path}"])

        for mount in spec.extra_mounts:
            if mount.mode == BoxHostMountMode.READ_ONLY:
                args.extend(["--bindmount_ro", f"{mount.host_path}:{mount.mount_path}"])
            elif mount.mode == BoxHostMountMode.READ_WRITE:
                args.extend(["--bindmount", f"{mount.host_path}:{mount.mount_path}"])

        # /tmp and /home are always per-session writable.
        tmp_dir = session_dir / "tmp"
        home_dir = session_dir / "home"
        args.extend(["--bindmount", f"{tmp_dir}:/tmp"])
        args.extend(["--bindmount", f"{home_dir}:/home"])

        return args

    def _ensure_chroot_mount_targets(
        self,
        root_dir: pathlib.Path,
        session: BoxSessionInfo,
        spec: BoxSpec,
    ) -> None:
        mount_paths = {
            "/proc",
            "/dev",
            "/tmp",
            "/home",
            spec.mount_path,
            session.mount_path,
        }
        mount_paths.update(_READONLY_SYSTEM_MOUNTS)
        mount_paths.update(_READONLY_ETC_ENTRIES)
        readonly_host_entries = set(_READONLY_SYSTEM_MOUNTS)
        readonly_host_entries.update(_READONLY_ETC_ENTRIES)
        for mount in spec.extra_mounts:
            mount_paths.add(mount.mount_path)

        for mount_path in mount_paths:
            if not mount_path:
                continue
            target = root_dir / mount_path.lstrip("/")
            try:
                if mount_path in readonly_host_entries and os.path.islink(mount_path):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    link_value = os.readlink(mount_path)
                    if os.path.lexists(target):
                        if target.is_symlink() and os.readlink(target) == link_value:
                            continue
                        if target.is_dir():
                            target.rmdir()
                        else:
                            target.unlink()
                    target.symlink_to(link_value)
                elif os.path.isfile(mount_path):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch(exist_ok=True)
                else:
                    target.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self.logger.debug(
                    f"Failed to prepare nsjail mount target {target}: {exc}"
                )

    def _build_resource_limits(self, spec: BoxSpec) -> list[str]:
        args: list[str] = []

        if self._cgroup_v2_available:
            # cgroup v2 – precise limits. nsjail defaults to the legacy cgroup
            # v1 layout, so we MUST opt into v2 explicitly; without this flag
            # nsjail tries to mkdir under /sys/fs/cgroup/<controller>/... (v1
            # paths) and aborts on a v2-only host. The writability of the v2
            # root is already verified in _detect_cgroup_v2().
            args.append("--use_cgroupv2")
            memory_bytes = spec.memory_mb * 1024 * 1024
            args.extend(["--cgroup_mem_max", str(memory_bytes)])
            # memory.max alone still permits the sandbox to push anonymous
            # pages into host swap. A tenant can otherwise exceed its
            # contracted memory budget and create system-wide swap thrashing.
            args.extend(["--cgroup_mem_swap_max", "0"])
            args.extend(["--cgroup_pids_max", str(spec.pids_limit)])
            cpu_ms = int(spec.cpus * 1000)
            args.extend(["--cgroup_cpu_ms_per_sec", str(cpu_ms)])
        else:
            # rlimit fallback – used whenever cgroup v2 delegation is not usable
            # (private cgroup namespace -> EBUSY, or read-only /sys/fs/cgroup).
            #
            # We do NOT set a SMALL --rlimit_as as a memory cap (see the
            # --rlimit_as hard note below). RLIMIT_AS limits *virtual* address
            # space, not resident memory, and modern runtimes reserve huge
            # virtual mappings up front: uv/Rust (and Go/JVM/Node) mmap
            # gigabytes of address space even to do tiny work, so a 512 MB
            # --rlimit_as aborts them instantly with
            # "memory allocation of N bytes failed" (exit 255) — which is what
            # silently broke every uvx-based stdio MCP server in containerized
            # nsjail deployments. There is no RSS-based rlimit on modern Linux
            # (RLIMIT_RSS is ignored), so accurate memory capping REQUIRES
            # cgroups. Operators who need a hard memory cap must run the Box
            # container in the host cgroup namespace (--cgroupns=host /
            # compose `cgroup: host`); otherwise bound memory at the container
            # level (e.g. compose `mem_limit`). We still apply the pid cap,
            # which is a real rlimit that does not break runtimes.
            args.extend(["--rlimit_nproc", str(spec.pids_limit)])

        # nsjail defaults --rlimit_as to 512 MB. RLIMIT_AS caps *virtual*
        # address space, and modern runtimes reserve huge virtual mappings up
        # front regardless of actual memory use: Node.js/V8 alone reserves well
        # over 512 MB of address space at startup, and its built-in undici HTTP
        # client instantiates an llhttp WebAssembly module during boot. Under
        # the default 512 MB RLIMIT_AS that WASM allocation fails with
        # "WebAssembly.instantiate(): Out of memory: Cannot allocate Wasm
        # memory for new instance", crashing every node/npx-based stdio MCP
        # server (e.g. firecrawl-mcp) even when cgroup_mem_max is generous.
        # Python/uvx servers reserve far less address space and were unaffected,
        # which made this look like "npx isn't supported".
        #
        # So we explicitly raise RLIMIT_AS to the current hard limit ("hard")
        # rather than leaving it at nsjail's small default. Real memory pressure
        # is still bounded by --cgroup_mem_max (cgroup v2 branch) or by the
        # container-level mem_limit (rlimit fallback branch) — both of which cap
        # RESIDENT memory, the thing that actually matters.
        args.extend(["--rlimit_as", "hard"])

        # Always set these rlimits regardless of cgroup mode. These are safe
        # for modern runtimes (unlike a small RLIMIT_AS).
        args.extend(["--rlimit_fsize", "512"])  # max file size 512 MB
        args.extend(["--rlimit_nofile", "256"])  # max open fds

        return args

    # ── process execution ─────────────────────────────────────────────

    async def _run_nsjail(
        self,
        args: list[str],
        timeout_sec: int,
    ) -> _CommandResult:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_task = asyncio.create_task(self._read_stream(process.stdout))
        stderr_task = asyncio.create_task(self._read_stream(process.stderr))

        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            timed_out = True
            # Let nsjail reap its children and remove their cgroups before exit.
            await self._terminate_process(process)
        except asyncio.CancelledError:
            await self._terminate_process(process)
            await asyncio.gather(
                stdout_task,
                stderr_task,
                return_exceptions=True,
            )
            raise

        stdout_bytes, stdout_total = await stdout_task
        stderr_bytes, stderr_total = await stderr_task

        return _CommandResult(
            return_code=process.returncode if not timed_out else -1,
            stdout=self._clip_captured_bytes(stdout_bytes, stdout_total),
            stderr=self._clip_captured_bytes(stderr_bytes, stderr_total),
            timed_out=timed_out,
        )

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _detect_cgroup_v2() -> bool:
        """Check whether nsjail's ``--use_cgroupv2`` path will actually work.

        nsjail (with ``--use_cgroupv2``) moves itself into a fresh child cgroup
        it ``mkdir``s under the cgroup v2 mount root, then enables controllers
        for that child by writing ``+memory`` (etc.) to the ROOT's
        ``cgroup.subtree_control``. BOTH operations must succeed.

        Probing ``mkdir`` alone is NOT sufficient and produces a false positive
        in the common containerized case: inside a **private** cgroup namespace
        (Docker/k8s default) the container's own cgroup root already contains
        live processes (the Box runtime itself), so the kernel's
        "no-internal-process" rule rejects the ``cgroup.subtree_control`` write
        with ``EBUSY`` even though ``mkdir`` under the root succeeds. nsjail then
        aborts and every sandbox launch exits 255. Conversely a read-only
        ``/sys/fs/cgroup`` (another common case) fails the ``mkdir``.

        So we probe the AUTHORITATIVE operation: a real write to
        ``cgroup.subtree_control``. We only consider it available when that
        write succeeds, which is exactly nsjail's requirement. Containerized
        deployments that need cgroup limits must run the Box container in the
        host cgroup namespace (``--cgroupns=host`` / compose ``cgroup: host``);
        otherwise this returns False and the backend uses the rlimit fallback.
        """
        cgroup_mount = pathlib.Path("/sys/fs/cgroup")
        if not cgroup_mount.exists():
            return False
        # cgroup v2 has a single hierarchy with a cgroup.controllers file.
        controllers = cgroup_mount / "cgroup.controllers"
        subtree_control = cgroup_mount / "cgroup.subtree_control"
        if not controllers.exists() or not subtree_control.exists():
            return False
        # nsjail always requests memory, pids, and cpu limits. Readiness must
        # therefore prove every controller is both available and writable;
        # accepting a partial delegation would fail after admission or silently
        # weaken the resource contract.
        try:
            available = set(controllers.read_text().split())
        except Exception:
            return False
        wanted = ("memory", "pids", "cpu")
        if not set(wanted).issubset(available):
            return False
        # Authoritative writability probe: re-arm a controller that is already
        # enabled (idempotent no-op), or briefly toggle one that is not. A
        # successful write proves nsjail's subtree_control write will also
        # succeed; EBUSY (private cgroupns) or EACCES/EROFS (read-only mount)
        # all surface here and correctly select the rlimit fallback.
        try:
            enabled = set(subtree_control.read_text().split())
        except Exception:
            return False
        for controller in wanted:
            try:
                # Already delegated: re-writing the same enable is a harmless
                # no-op that still exercises the write permission + EBUSY rule.
                subtree_control.write_text(f"+{controller}")
            except Exception:
                return False
            if controller not in enabled:
                # Not yet delegated: immediately disable it again so the probe
                # leaves the host configuration unchanged.
                try:
                    subtree_control.write_text(f"-{controller}")
                except Exception as exc:
                    _LOGGER.warning(
                        "Failed to restore cgroup controller delegation after probe: controller=%s error=%s",
                        controller,
                        exc,
                    )
                    return False
        return True

    async def _kill_session_processes(self, session_dir: pathlib.Path) -> None:
        """Best-effort kill of nsjail processes associated with a session dir.

        We scan /proc for nsjail processes whose command line contains the
        session directory path.
        """
        await bounded_executor.run_blocking_cleanup(
            self._kill_session_processes_sync,
            session_dir,
        )

    def _kill_session_processes_sync(self, session_dir: pathlib.Path) -> None:
        session_path_str = str(session_dir)
        proc_dir = pathlib.Path("/proc")
        if not proc_dir.exists():
            return

        for pid_dir in proc_dir.iterdir():
            if not pid_dir.name.isdigit():
                continue
            try:
                cmdline = (
                    (pid_dir / "cmdline").read_bytes().decode("utf-8", errors="replace")
                )
                if self._nsjail_bin in cmdline and session_path_str in cmdline:
                    pid = int(pid_dir.name)
                    os.kill(pid, signal.SIGKILL)
                    self.logger.info(f"Killed orphaned nsjail process {pid}")
            except (OSError, ValueError):
                continue

    def _kill_orphaned_session_processes_sync(
        self,
        current_instance_id: str,
        *,
        proc_dir: pathlib.Path | None = None,
    ) -> None:
        """Kill nsjail processes under stale session directories in one pass."""

        proc_dir = proc_dir or pathlib.Path("/proc")
        if not current_instance_id or not proc_dir.exists():
            return
        base_prefix = f"{self._base_dir}{os.sep}"
        current_prefix = f"{current_instance_id}_"
        for pid_dir in proc_dir.iterdir():
            if not pid_dir.name.isdigit():
                continue
            try:
                cmdline = (
                    (pid_dir / "cmdline").read_bytes().decode("utf-8", errors="replace")
                )
                if self._nsjail_bin not in cmdline:
                    continue
                tail = cmdline.partition(base_prefix)[2]
                if not tail:
                    continue
                session_name = tail.split("/", 1)[0].split("\0", 1)[0]
                if not session_name:
                    continue
                if not session_name.startswith(current_prefix):
                    continue
                if not self._session_owned_by(
                    self._base_dir / session_name, current_instance_id
                ):
                    continue
                pid = int(pid_dir.name)
                os.kill(pid, signal.SIGKILL)
                self.logger.info(f"Killed orphaned nsjail process {pid}")
            except (OSError, ValueError):
                continue
