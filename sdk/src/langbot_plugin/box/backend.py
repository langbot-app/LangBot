from __future__ import annotations

import abc
import asyncio
import dataclasses
import datetime as dt
import logging
import os
import re
import shlex
import shutil
import uuid
import tempfile

from ..artifact import materialize_tree
from ..runtime import bounded_executor

from .errors import BoxError
from .models import (
    ARTIFACT_MOUNT_ROOT,
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxNetworkMode,
    BoxSessionInfo,
    BoxSpec,
)
from .security import validate_sandbox_security

# Hard cap on raw subprocess output to prevent unbounded memory usage.
# Container timeout already bounds duration, but fast commands can still
# produce large output within the time limit.  After this many bytes the
# remaining output is discarded before decoding.
_MAX_RAW_OUTPUT_BYTES = 1_048_576  # 1 MB per stream
_FALSE_VALUES = {"0", "false"}


@dataclasses.dataclass(slots=True)
class _CommandResult:
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class BaseSandboxBackend(abc.ABC):
    name: str
    instance_id: str = ""
    execution_scoped_mounts: bool = False
    content_addressed_mounts: bool = False

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def initialize(self):
        return None

    @abc.abstractmethod
    async def is_available(self) -> bool:
        pass

    @abc.abstractmethod
    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        pass

    @abc.abstractmethod
    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        pass

    @abc.abstractmethod
    async def stop_session(self, session: BoxSessionInfo):
        pass

    async def is_session_alive(self, session: BoxSessionInfo) -> bool:
        return True

    async def get_readiness(
        self,
        *,
        workspace_path: str | None = None,
        strict: bool = False,
    ) -> dict:
        """Return backend isolation readiness.

        Generic backends can report availability, but cannot claim the
        cgroup/namespace/mount guarantees required by the managed nsjail mode.
        """

        available = await self.is_available()
        return {
            "available": available,
            "cgroup_v2": False if strict else None,
            "namespace_isolation": False if strict else None,
            "mount_isolation": False if strict else None,
            "network_isolation": False if strict else None,
            "hard_workspace_quota": False if strict else None,
            "hard_read_only_mount_quota": False if strict else None,
            "bounded_ephemeral_storage": False if strict else None,
            "inode_quota": False if strict else None,
        }

    async def start_managed_process(self, session: BoxSessionInfo, spec):
        raise BoxError(f"{self.name} backend does not support managed processes")

    async def cleanup_orphaned_containers(self, current_instance_id: str = ""):
        """Remove lingering containers from previous runs. No-op by default."""
        pass

    @staticmethod
    def _clip_captured_bytes(
        data: bytes, total_size: int, limit: int = _MAX_RAW_OUTPUT_BYTES
    ) -> str:
        text = data.decode("utf-8", errors="replace").strip()
        if total_size > limit:
            text += f"\n... [raw output clipped at {limit} bytes, {total_size - limit} bytes discarded]"
        return text

    @staticmethod
    async def _read_stream(
        stream: asyncio.StreamReader | None,
        limit: int = _MAX_RAW_OUTPUT_BYTES,
    ) -> tuple[bytes, int]:
        if stream is None:
            return b"", 0

        chunks = bytearray()
        total_size = 0
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            total_size += len(chunk)
            remaining = limit - len(chunks)
            if remaining > 0:
                chunks.extend(chunk[:remaining])

        return bytes(chunks), total_size

    @staticmethod
    async def _terminate_process(
        process: asyncio.subprocess.Process,
        *,
        timeout_sec: float = 2.0,
    ) -> None:
        """Terminate and reap a cancelled backend CLI without orphaning it."""

        if process.returncode is not None:
            return
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()


class CLISandboxBackend(BaseSandboxBackend):
    content_addressed_mounts = True
    command: str

    def __init__(self, logger: logging.Logger, command: str, backend_name: str):
        super().__init__(logger)
        self.command = command
        self.name = backend_name
        self.cpu_limit_enabled = True
        self.artifact_cache_parent: str | None = None
        self._artifact_roots: dict[str, str] = {}
        self._availability_task: asyncio.Task[bool] | None = None
        self._availability_waiters: dict[asyncio.Task[bool], int] = {}

    async def is_available(self) -> bool:
        if shutil.which(self.command) is None:
            return False

        task = self._availability_task
        if task is None or task.done():
            task = asyncio.create_task(self._probe_availability())
            self._availability_task = task
        self._availability_waiters[task] = self._availability_waiters.get(task, 0) + 1
        try:
            # Share only in-flight work; cancelling one query must not cancel others.
            return await asyncio.shield(task)
        finally:
            self._availability_waiters[task] -= 1
            if not self._availability_waiters[task]:
                del self._availability_waiters[task]
                if self._availability_task is task:
                    self._availability_task = None
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def _probe_availability(self) -> bool:
        result = await self._run_command(
            [self.command, "info"], timeout_sec=5, check=False
        )
        return result.return_code == 0 and not result.timed_out

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        validate_sandbox_security(spec)

        now = dt.datetime.now(dt.timezone.utc)
        container_name = self._build_container_name(spec.session_id)

        args = [
            self.command,
            "run",
            "-d",
        ]

        if not spec.persistent:
            args.append("--rm")

        args.extend(
            [
                "--name",
                container_name,
                "--label",
                "langbot.box=true",
                "--label",
                f"langbot.session_id={spec.session_id}",
                "--label",
                f"langbot.box.instance_id={self.instance_id}",
            ]
        )

        if spec.network == BoxNetworkMode.OFF:
            args.extend(["--network", "none"])

        args.extend(self._build_resource_limit_args(spec))

        if spec.read_only_rootfs:
            args.append("--read-only")
            args.extend(["--tmpfs", "/tmp:size=64m"])

        if spec.host_path is not None and spec.host_path_mode != BoxHostMountMode.NONE:
            os.makedirs(spec.host_path, exist_ok=True)
            mount_spec = (
                f"{spec.host_path}:{spec.mount_path}:{spec.host_path_mode.value}"
            )
            args.extend(["-v", mount_spec])

        # Bind sources are resolved by the daemon, not this process. When a
        # shared host root is configured, the cache must live there as well.
        if self.artifact_cache_parent is not None:
            os.makedirs(self.artifact_cache_parent, exist_ok=True)
        artifact_root = tempfile.mkdtemp(
            prefix="langbot-box-artifacts-", dir=self.artifact_cache_parent
        )
        os.chmod(artifact_root, 0o755)
        self._artifact_roots[container_name] = artifact_root
        args.extend(["-v", f"{artifact_root}:{ARTIFACT_MOUNT_ROOT}:ro"])
        for mount in spec.extra_mounts:
            if mount.mode != BoxHostMountMode.NONE and not mount.is_content_addressed:
                args.extend(
                    ["-v", f"{mount.host_path}:{mount.mount_path}:{mount.mode.value}"]
                )

        args.extend([spec.image, "sh", "-lc", "while true; do sleep 3600; done"])

        self.logger.info(
            f"LangBot Box backend start_session: backend={self.name} "
            f"session_id={spec.session_id} container_name={container_name} "
            f"image={spec.image} network={spec.network.value} "
            f"host_path={spec.host_path} host_path_mode={spec.host_path_mode.value} mount_path={spec.mount_path} "
            f"cpus={spec.cpus} cpu_limit_enabled={self.cpu_limit_enabled} "
            f"memory_mb={spec.memory_mb} pids_limit={spec.pids_limit} "
            f"read_only_rootfs={spec.read_only_rootfs} workspace_quota_mb={spec.workspace_quota_mb}"
        )

        start_task = None
        try:
            await self._prepare_artifacts(container_name, spec)
            start_task = asyncio.create_task(
                self._run_command(args, timeout_sec=30, check=True)
            )
            await asyncio.shield(start_task)
        except BaseException:
            if start_task is not None:
                try:
                    await start_task
                except BaseException:
                    pass
                await self._run_command(
                    [self.command, "rm", "-f", container_name],
                    timeout_sec=20,
                    check=False,
                )
            self._artifact_roots.pop(container_name, None)
            shutil.rmtree(artifact_root)
            raise

        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=container_name,
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

    async def _prepare_artifacts(self, session_id: str, spec: BoxSpec) -> None:
        for mount in spec.extra_mounts:
            if mount.is_content_addressed:
                root = self._artifact_roots.get(session_id)
                if root is None:
                    raise BoxError(
                        "Immutable artifact cache is unavailable; acquire a new Box"
                    )
                try:
                    await bounded_executor.run_blocking_atomic(
                        materialize_tree,
                        mount.host_path,
                        mount.manifest_path,
                        mount.content_digest,
                        root,
                    )
                except (OSError, ValueError) as exc:
                    raise BoxError(
                        f"Immutable artifact preparation failed: {exc}"
                    ) from exc

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        await self._prepare_artifacts(session.backend_session_id, spec)
        start = dt.datetime.now(dt.timezone.utc)
        args = [self.command, "exec"]

        for key, value in spec.env.items():
            args.extend(["-e", f"{key}={value}"])

        command = self._build_exec_command(spec.workdir, spec.cmd)
        # Attachment manifests can exceed Windows CreateProcess limits (and
        # POSIX per-argument limits). Keep large scripts out of argv.
        input_data = None
        if len(command.encode("utf-8")) > 8192:
            args.append("-i")
            input_data = command.encode("utf-8")
            command = 'exec sh -lc "$(cat)"'
        args.extend([session.backend_session_id, "sh", "-lc", command])

        cmd_preview = spec.cmd.strip()
        if len(cmd_preview) > 400:
            cmd_preview = f"{cmd_preview[:397]}..."
        self.logger.info(
            f"LangBot Box backend exec: backend={self.name} "
            f"session_id={session.session_id} container_name={session.backend_session_id} "
            f"workdir={spec.workdir} timeout_sec={spec.timeout_sec} "
            f"env_keys={sorted(spec.env.keys())} cmd={cmd_preview}"
        )

        run_options = {"input_data": input_data} if input_data is not None else {}
        result = await self._run_command(
            args, timeout_sec=spec.timeout_sec, check=False, **run_options
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

    async def stop_session(self, session: BoxSessionInfo):
        self.logger.info(
            f"LangBot Box backend stop_session: backend={self.name} "
            f"session_id={session.session_id} container_name={session.backend_session_id}"
        )
        result = await self._run_command(
            [self.command, "rm", "-f", session.backend_session_id],
            timeout_sec=20,
            check=False,
        )
        if result.return_code != 0 or result.timed_out:
            # A missing container is already stopped; daemon failures are not.
            remaining = await self._run_command(
                [
                    self.command,
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
            if (
                remaining.timed_out
                or remaining.return_code != 0
                or session.backend_session_id in remaining.stdout.splitlines()
            ):
                raise BoxError(
                    self._format_cli_error(
                        result.stderr
                        or f"Failed to remove container {session.backend_session_id}"
                    )
                )
        root = self._artifact_roots.get(session.backend_session_id)
        if root is not None:
            await bounded_executor.run_blocking_cleanup(shutil.rmtree, root)
            self._artifact_roots.pop(session.backend_session_id, None)

    async def is_session_alive(self, session: BoxSessionInfo) -> bool:
        result = await self._run_command(
            [
                self.command,
                "inspect",
                "-f",
                "{{.State.Running}}",
                session.backend_session_id,
            ],
            timeout_sec=5,
            check=False,
        )
        return result.return_code == 0 and result.stdout.strip().lower() == "true"

    async def cleanup_orphaned_containers(self, current_instance_id: str = ""):
        """Remove only containers left by this instance's previous run."""
        if not current_instance_id:
            return
        self.logger.info(
            "Box cleanup scoped to instance %s; other owners and unlabeled containers are retained",
            current_instance_id,
        )
        result = await self._run_command(
            [
                self.command,
                "ps",
                "-a",
                "--filter",
                "label=langbot.box=true",
                "--filter",
                f"label=langbot.box.instance_id={current_instance_id}",
                "--format",
                '{{.ID}}\t{{.Label "langbot.box.instance_id"}}',
            ],
            timeout_sec=10,
            check=False,
        )
        if result.return_code != 0 or not result.stdout.strip():
            return
        orphan_ids = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            cid = parts[0].strip()
            label_instance = parts[1].strip() if len(parts) > 1 else ""
            if label_instance == current_instance_id:
                orphan_ids.append(cid)
            else:
                self.logger.debug(
                    "Skipping Box container %s: different or missing instance ID", cid
                )
        if not orphan_ids:
            return
        for cid in orphan_ids:
            self.logger.info(f"Cleaning up orphaned Box container: {cid}")
        await self._run_command(
            [self.command, "rm", "-f", *orphan_ids],
            timeout_sec=30,
            check=False,
        )

    async def start_managed_process(
        self, session: BoxSessionInfo, spec
    ) -> asyncio.subprocess.Process:
        args = [self.command, "exec", "-i"]

        for key, value in spec.env.items():
            args.extend(["-e", f"{key}={value}"])

        args.extend(
            [
                session.backend_session_id,
                "sh",
                "-lc",
                self._build_spawn_command(spec.cwd, spec.command, spec.args),
            ]
        )

        self.logger.info(
            f"LangBot Box backend start_managed_process: backend={self.name} "
            f"session_id={session.session_id} container_name={session.backend_session_id} "
            f"cwd={spec.cwd} env_keys={sorted(spec.env.keys())} command={spec.command} args={spec.args}"
        )

        return await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    def _build_container_name(self, session_id: str) -> str:
        normalized = (
            re.sub(r"[^a-zA-Z0-9_.-]+", "-", session_id).strip("-").lower() or "session"
        )
        suffix = uuid.uuid4().hex[:8]
        return f"langbot-box-{normalized[:32]}-{suffix}"

    def _build_resource_limit_args(self, spec: BoxSpec) -> list[str]:
        args: list[str] = []
        if self.cpu_limit_enabled:
            args.extend(["--cpus", str(spec.cpus)])
        args.extend(["--memory", f"{spec.memory_mb}m"])
        args.extend(["--pids-limit", str(spec.pids_limit)])
        return args

    def _build_exec_command(self, workdir: str, cmd: str) -> str:
        quoted_workdir = shlex.quote(workdir)
        return f"mkdir -p {quoted_workdir} && cd {quoted_workdir} && {cmd}"

    def _build_spawn_command(self, cwd: str, command: str, args: list[str]) -> str:
        quoted_cwd = shlex.quote(cwd)
        command_parts = [shlex.quote(command), *[shlex.quote(arg) for arg in args]]
        return f"mkdir -p {quoted_cwd} && cd {quoted_cwd} && exec {' '.join(command_parts)}"

    async def _run_command(
        self,
        args: list[str],
        timeout_sec: int,
        check: bool,
        input_data: bytes | None = None,
    ) -> _CommandResult:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if input_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_task = asyncio.create_task(self._read_stream(process.stdout))
        stderr_task = asyncio.create_task(self._read_stream(process.stderr))

        async def feed_and_wait():
            if input_data is not None:
                try:
                    process.stdin.write(input_data)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    process.stdin.close()
            await process.wait()

        timed_out = False
        try:
            await asyncio.wait_for(feed_and_wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            process.kill()
            timed_out = True
            await process.wait()
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

        if timed_out:
            return _CommandResult(
                return_code=-1,
                stdout=self._clip_captured_bytes(stdout_bytes, stdout_total),
                stderr=self._clip_captured_bytes(stderr_bytes, stderr_total),
                timed_out=True,
            )

        stdout = self._clip_captured_bytes(stdout_bytes, stdout_total)
        stderr = self._clip_captured_bytes(stderr_bytes, stderr_total)

        if check and process.returncode != 0:
            raise BoxError(
                self._format_cli_error(stderr or stdout or "unknown backend error")
            )

        return _CommandResult(
            return_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
        )

    def _format_cli_error(self, message: str) -> str:
        message = " ".join(message.split())
        if len(message) > 300:
            message = f"{message[:297]}..."
        return f"{self.name} backend error: {message}"


class DockerBackend(CLISandboxBackend):
    def __init__(self, logger: logging.Logger):
        super().__init__(logger=logger, command="docker", backend_name="docker")

    def configure(self, config: dict) -> None:
        raw_value = config.get("cpu_limit_enabled", True)
        if isinstance(raw_value, bool):
            enabled = raw_value
        else:
            enabled = str(raw_value).strip().lower() not in _FALSE_VALUES
        self.cpu_limit_enabled = enabled
        if not enabled:
            self.logger.warning(
                "Docker sandbox CPU limit is disabled by config "
                "(box.docker.cpu_limit_enabled=false); containers will be started without --cpus."
            )
