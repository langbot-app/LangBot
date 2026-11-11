from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import logging
import os
import posixpath
import re
import shlex
import shutil
import signal
import tempfile
import uuid

from .backend import BaseSandboxBackend, _CommandResult
from .errors import BoxError, BoxValidationError
from .models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxSessionInfo,
    BoxSpec,
)
from .security import validate_sandbox_security

_UTC = dt.timezone.utc
_INHERITED_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM")


@dataclasses.dataclass(slots=True)
class _HostSession:
    root_path: str
    home_path: str
    tmp_path: str
    workspace_path: str
    mounts: tuple[tuple[str, str], ...]


class _HostManagedProcess:
    """Process facade whose terminate/kill operations cover its process group."""

    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process
        self.stdin = process.stdin
        self.stdout = process.stdout
        self.stderr = process.stderr

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    def terminate(self) -> None:
        os.killpg(self._process.pid, signal.SIGTERM)

    def kill(self) -> None:
        os.killpg(self._process.pid, signal.SIGKILL)

    async def wait(self) -> int:
        return await self._process.wait()


class HostProcessBackend(BaseSandboxBackend):
    """Explicitly unsafe backend that runs Box commands on the Runtime host."""

    execution_scoped_mounts = True
    name = "host"
    unsafe_direct_execution = True

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self._shell = shutil.which("sh")
        self._sessions: dict[str, _HostSession] = {}

    async def initialize(self):
        self.logger.warning(
            "LangBot Box host backend is UNSAFE: commands run with the Box "
            "Runtime user's host permissions and have no filesystem, network, "
            "process, or resource isolation"
        )

    async def is_available(self) -> bool:
        return os.name == "posix" and self._shell is not None

    async def get_readiness(
        self,
        *,
        workspace_path: str | None = None,
        strict: bool = False,
    ) -> dict:
        return {
            "available": await self.is_available(),
            "unsafe_direct_execution": True,
            "cgroup_v2": False,
            "namespace_isolation": False,
            "mount_isolation": False,
            "network_isolation": False,
            "hard_workspace_quota": False,
            "hard_read_only_mount_quota": False,
            "bounded_ephemeral_storage": False,
            "inode_quota": False,
        }

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        if not await self.is_available():
            raise BoxError("host backend requires a POSIX system with sh on PATH")
        validate_sandbox_security(spec)

        root_path = tempfile.mkdtemp(prefix="langbot-box-host-")
        home_path = os.path.join(root_path, "home")
        tmp_path = os.path.join(root_path, "tmp")
        os.makedirs(home_path)
        os.makedirs(tmp_path)

        if spec.host_path and spec.host_path_mode != BoxHostMountMode.NONE:
            workspace_path = os.path.realpath(spec.host_path)
            os.makedirs(workspace_path, exist_ok=True)
        else:
            workspace_path = os.path.join(root_path, "workspace")
            os.makedirs(workspace_path)

        mounts = {posixpath.normpath(spec.mount_path): workspace_path}
        for mount in spec.extra_mounts:
            if mount.mode != BoxHostMountMode.NONE:
                mounts[posixpath.normpath(mount.mount_path)] = os.path.realpath(
                    mount.host_path
                )
        ordered_mounts = tuple(
            sorted(mounts.items(), key=lambda item: len(item[0]), reverse=True)
        )

        backend_session_id = f"host-{uuid.uuid4().hex[:12]}"
        self._sessions[backend_session_id] = _HostSession(
            root_path=root_path,
            home_path=home_path,
            tmp_path=tmp_path,
            workspace_path=workspace_path,
            mounts=ordered_mounts,
        )

        now = dt.datetime.now(_UTC)
        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=backend_session_id,
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
        state = self._require_session(session)
        mounts = {posixpath.normpath(spec.mount_path): state.workspace_path}
        mounts.update(
            {
                mount.mount_path: os.path.realpath(mount.host_path)
                for mount in spec.extra_mounts
                if mount.mode != BoxHostMountMode.NONE
            }
        )
        state = dataclasses.replace(
            state,
            mounts=tuple(
                sorted(mounts.items(), key=lambda item: len(item[0]), reverse=True)
            ),
        )
        workdir = self._map_path(state, spec.workdir)
        os.makedirs(workdir, exist_ok=True)
        command = self._rewrite_shell_paths(state, spec.cmd)
        start = dt.datetime.now(_UTC)

        self.logger.info(
            "LangBot Box host exec: session_id=%s workdir=%s timeout_sec=%s "
            "env_keys=%s cmd=%s",
            session.session_id,
            spec.workdir,
            spec.timeout_sec,
            sorted(spec.env),
            self._preview(spec.cmd),
        )
        result = await self._run_shell(
            command,
            cwd=workdir,
            env=self._build_env(state, spec.env),
            timeout_sec=spec.timeout_sec,
        )
        duration_ms = int((dt.datetime.now(_UTC) - start).total_seconds() * 1000)
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

    async def start_managed_process(
        self, session: BoxSessionInfo, spec
    ) -> _HostManagedProcess:
        state = self._require_session(session)
        cwd = self._map_path(state, spec.cwd)
        os.makedirs(cwd, exist_ok=True)
        command = self._map_path(state, spec.command)
        args = [self._rewrite_argument_paths(state, arg) for arg in spec.args]
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            cwd=cwd,
            env=self._build_env(state, spec.env),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        return _HostManagedProcess(process)

    async def stop_session(self, session: BoxSessionInfo):
        state = self._sessions.pop(session.backend_session_id, None)
        if state is not None:
            shutil.rmtree(state.root_path, ignore_errors=True)

    async def is_session_alive(self, session: BoxSessionInfo) -> bool:
        return session.backend_session_id in self._sessions

    def _require_session(self, session: BoxSessionInfo) -> _HostSession:
        state = self._sessions.get(session.backend_session_id)
        if state is None:
            raise BoxError(f"host session {session.session_id} is not available")
        return state

    @staticmethod
    def _map_path(state: _HostSession, path: str) -> str:
        normalized = posixpath.normpath(path)
        claimed_mount = False
        for mount_path, host_path in state.mounts:
            if path == mount_path or path.startswith(f"{mount_path}/"):
                claimed_mount = True
            if normalized == mount_path or normalized.startswith(f"{mount_path}/"):
                relative = normalized[len(mount_path) :].lstrip("/")
                candidate = os.path.realpath(os.path.join(host_path, relative))
                try:
                    if os.path.commonpath((candidate, host_path)) != host_path:
                        raise BoxValidationError(
                            f"host backend path escapes mount {mount_path}"
                        )
                except ValueError as exc:
                    raise BoxValidationError(
                        f"host backend path escapes mount {mount_path}"
                    ) from exc
                return candidate
        if claimed_mount:
            raise BoxValidationError("host backend path escapes its mounted workspace")
        return path

    @classmethod
    def _rewrite_shell_paths(cls, state: _HostSession, command: str) -> str:
        for _, host_path in state.mounts:
            if shlex.quote(host_path) != host_path:
                raise BoxValidationError(
                    "host backend requires mount paths without shell-special characters"
                )
        return cls._replace_mount_paths(state, command)

    @classmethod
    def _rewrite_argument_paths(cls, state: _HostSession, value: str) -> str:
        return cls._replace_mount_paths(state, value)

    @staticmethod
    def _replace_mount_paths(state: _HostSession, value: str) -> str:
        if not state.mounts:
            return value
        alternatives = "|".join(re.escape(item[0]) for item in state.mounts)
        pattern = re.compile(rf"(?P<mount>{alternatives})(?=/|$|[^A-Za-z0-9_.-])")
        mapped = dict(state.mounts)
        return pattern.sub(lambda match: mapped[match.group("mount")], value)

    @staticmethod
    def _build_env(state: _HostSession, extra: dict[str, str]) -> dict[str, str]:
        env = {key: os.environ[key] for key in _INHERITED_ENV_KEYS if key in os.environ}
        env.setdefault("PATH", os.defpath)
        env.update(
            {
                "HOME": state.home_path,
                "TMPDIR": state.tmp_path,
                "LANGBOT_BOX_WORKSPACE": state.workspace_path,
            }
        )
        env.update(extra)
        return env

    async def _run_shell(
        self,
        command: str,
        *,
        cwd: str,
        env: dict[str, str],
        timeout_sec: int,
    ) -> _CommandResult:
        assert self._shell is not None
        process = await asyncio.create_subprocess_exec(
            self._shell,
            "-lc",
            command,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        completion = asyncio.gather(
            process.wait(),
            self._read_stream(process.stdout),
            self._read_stream(process.stderr),
        )
        timed_out = False
        try:
            # Descendants can keep output pipes open after the shell exits.
            # Keep readers alive during cleanup to preserve captured output.
            await asyncio.wait_for(asyncio.shield(completion), timeout=timeout_sec)
        except asyncio.TimeoutError:
            timed_out = True
            await self._terminate_process_group(process)
        except asyncio.CancelledError:
            await self._terminate_process_group(process)
            await completion
            raise

        _, (stdout_bytes, stdout_total), (stderr_bytes, stderr_total) = await completion
        return _CommandResult(
            return_code=process.returncode if process.returncode is not None else -1,
            stdout=self._clip_captured_bytes(stdout_bytes, stdout_total),
            stderr=self._clip_captured_bytes(stderr_bytes, stderr_total),
            timed_out=timed_out,
        )

    @staticmethod
    async def _terminate_process_group(
        process: asyncio.subprocess.Process,
        *,
        timeout_sec: float = 2.0,
    ) -> None:
        """Terminate the isolated group even if its shell has already exited."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_sec
        try:
            os.killpg(process.pid, signal.SIGTERM)
            # A shell exit does not mean descendants exited or closed their pipes.
            while True:
                os.killpg(process.pid, 0)
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(0.05, remaining))
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    @staticmethod
    def _preview(command: str) -> str:
        command = command.strip()
        return command if len(command) <= 400 else f"{command[:397]}..."
