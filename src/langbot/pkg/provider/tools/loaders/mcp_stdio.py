from __future__ import annotations

import enum
import asyncio
import os
import shutil
import shlex
import threading
from contextlib import suppress, AsyncExitStack
from typing import TYPE_CHECKING, Any

import pydantic
from mcp import ClientSession
from mcp.client.websocket import websocket_client
from ....box.workspace import (
    BoxWorkspaceSession,
    classify_python_workspace,
    infer_workspace_host_path,
    normalize_host_path,
    rewrite_mounted_path,
    rewrite_venv_command,
    unwrap_venv_path,
    wrap_python_command_with_env,
)

if TYPE_CHECKING:
    from .mcp import RuntimeMCPSession


_WORKSPACE_COPY_LOCKS: dict[str, threading.Lock] = {}
_WORKSPACE_COPY_LOCKS_GUARD = threading.Lock()


def _workspace_copy_lock(path: str) -> threading.Lock:
    with _WORKSPACE_COPY_LOCKS_GUARD:
        lock = _WORKSPACE_COPY_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _WORKSPACE_COPY_LOCKS[path] = lock
        return lock


class MCPSessionErrorPhase(enum.Enum):
    """Which phase of the MCP lifecycle failed."""

    SESSION_CREATE = 'session_create'
    DEP_INSTALL = 'dep_install'
    PROCESS_START = 'process_start'
    RELAY_CONNECT = 'relay_connect'
    MCP_INIT = 'mcp_init'
    RUNTIME = 'runtime'
    TOOL_CALL = 'tool_call'
    # Stdio MCP refused because Box is disabled in config or currently
    # unavailable. Not transient — retries would be pointless. The frontend
    # uses this phase to render a localized actionable message instead of
    # the raw RuntimeError text.
    BOX_UNAVAILABLE = 'box_unavailable'


class MCPServerBoxConfig(pydantic.BaseModel):
    """Structured configuration for running an MCP server inside a Box container."""

    image: str | None = None
    network: str = 'on'  # MCP servers need network for dependency installation
    host_path: str | None = None
    host_path_mode: str = 'ro'  # MCP servers default to read-write mount only when explicitly requested
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    startup_timeout_sec: int = 300  # First Docker bootstrap may need to build a venv and install MCP deps.
    cpus: float | None = None
    memory_mb: int | None = None
    pids_limit: int | None = None
    read_only_rootfs: bool | None = None

    model_config = pydantic.ConfigDict(extra='ignore')


_HANDSHAKE_ATTEMPT_TIMEOUT_SEC = 10.0


class _TransferredStack:
    """Adapts an already-populated AsyncExitStack into an async context manager
    so ownership of its resources can be transferred into another exit stack.
    Entering is a no-op; exiting closes the wrapped stack (and thus the live WS
    transport + ClientSession) when the owning session shuts down."""

    def __init__(self, stack: AsyncExitStack):
        self._stack = stack

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._stack.aclose()
        return False


class _ColdStartRetry(Exception):
    """Signal: the managed process is alive but not yet answering the MCP
    handshake because it is still cold-starting (e.g. `npx -y <pkg>` is still
    installing). The outer lifecycle retry treats this like a transient
    reconnect: it reuses the live process and does not count toward the fatal
    retry budget, so a slow cold start is waited out rather than failing.
    """


class BoxStdioSessionRuntime:
    """Encapsulate Box-backed stdio MCP session orchestration."""

    def __init__(self, owner: RuntimeMCPSession):
        self.owner = owner
        self.config = MCPServerBoxConfig.model_validate(owner.server_config.get('box', {}))

    @property
    def ap(self):
        return self.owner.ap

    @property
    def server_name(self) -> str:
        return self.owner.server_name

    @property
    def server_config(self) -> dict:
        return self.owner.server_config

    def _build_workspace(
        self,
        *,
        host_path: str | None | object = ...,
        workdir: str = '/workspace',
        mount_path: str = '/workspace',
    ) -> BoxWorkspaceSession:
        resolved_host_path = self.resolve_host_path() if host_path is ... else host_path
        return BoxWorkspaceSession(
            self.ap.box_service,
            self.owner._build_box_session_id(),
            host_path=resolved_host_path,
            host_path_mode=self.config.host_path_mode,
            workdir=workdir,
            env=self.config.env,
            mount_path=mount_path,
            network=self.config.network,
            read_only_rootfs=self.config.read_only_rootfs if self.config.read_only_rootfs is not None else False,
            image=self.config.image,
            cpus=self.config.cpus,
            # Node.js runtimes (npx/bunx) reserve large virtual address space and
            # load WebAssembly modules (llhttp) on startup; the default 512 MB
            # cgroup_mem_max is too small and causes OOM kills (return_code=137).
            # Auto-bump to 1024 MB when the runner is npx/bunx/pnpm dlx.
            memory_mb=self.config.memory_mb or 1024,
            pids_limit=self.config.pids_limit,
            persistent=True,
        )

    @property
    def process_id(self) -> str:
        """Each MCP server gets a unique process_id within the shared session."""
        return self.owner.server_uuid

    def uses_box_stdio(self) -> bool:
        if self.server_config.get('mode') != 'stdio':
            return False
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None:
            return False
        # When Box is configured but currently unavailable (disabled or
        # connection failed), do NOT silently fall through to host-stdio —
        # that would bypass the sandbox the operator asked for. The caller
        # is expected to refuse the stdio MCP server with a clear error.
        return bool(getattr(box_service, 'available', False))

    async def initialize(self) -> None:
        await self._wait_for_box_runtime()

        # All stdio MCP servers share one Box session. Per-server host paths
        # are staged into the shared workspace instead of becoming session
        # mounts, because an existing Docker container cannot add bind mounts.
        workspace = self._build_workspace(host_path=None)
        host_path = self.resolve_host_path()
        process_cwd = '/workspace'
        install_cmd: str | None = None

        try:
            await workspace.create_session()
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.SESSION_CREATE
            raise

        if host_path:
            process_cwd = await self._stage_host_path_to_shared_workspace(host_path)
            install_cmd = self.detect_install_command(host_path, process_cwd)
            if install_cmd:
                self.ap.logger.info(
                    f'MCP server {self.server_name}: installing dependencies in Box with: {install_cmd}'
                )
                try:
                    result = await workspace.execute_raw(
                        install_cmd,
                        workdir=process_cwd,
                        timeout_sec=self.config.startup_timeout_sec or 120,
                    )
                except Exception:
                    self.owner.error_phase = MCPSessionErrorPhase.DEP_INSTALL
                    raise
                if not result.ok:
                    self.owner.error_phase = MCPSessionErrorPhase.DEP_INSTALL
                    stderr_preview = (result.stderr or '')[:500]
                    raise Exception(f'Dependency install failed (exit code {result.exit_code}): {stderr_preview}')

        # Reuse an already-running managed process instead of rebuilding it.
        # The Box runtime keeps the managed process alive across a transient
        # WebSocket transport drop, so on a reconnect we only need to re-attach
        # the WS below. Rebuilding here would needlessly stop a healthy process
        # and re-run the (slow, network-touching) dependency bootstrap.
        if not await self._managed_process_is_running():
            try:
                process_workspace = (
                    self._build_workspace(host_path=host_path, workdir=process_cwd, mount_path=process_cwd)
                    if host_path
                    else workspace
                )
                payload = process_workspace.build_process_payload(
                    self.server_config['command'],
                    self.server_config.get('args', []),
                    env=self.server_config.get('env', {}),
                    cwd=process_cwd,
                )
                if install_cmd:
                    payload = self._wrap_process_payload_with_python_env(payload, process_cwd)
                payload['process_id'] = self.process_id
                await workspace.box_service.start_managed_process(workspace.session_id, payload)
            except Exception:
                self.owner.error_phase = MCPSessionErrorPhase.PROCESS_START
                raise
        else:
            self.ap.logger.info(
                f'MCP server {self.server_name}: reusing live managed process '
                f'process_id={self.process_id} (transport reconnect)'
            )

        websocket_url = workspace.get_managed_process_websocket_url(self.process_id)

        # Attach the WS transport + MCP session ONCE, on the owner's exit stack,
        # in the same task as the serve loop that follows. websocket_client and
        # ClientSession use anyio task groups whose cancel scope is bound to the
        # frame/stack that entered them, so they must live on the owner exit
        # stack (not a deferred/transferred one) or the streams close the moment
        # initialize() returns and the next request fails with "Connection
        # closed".
        #
        # A slow (`npx -y <pkg>`) cold start makes this single attempt fail
        # while the process is still alive — the package is still installing and
        # cannot answer the handshake. We surface that to the outer retry loop
        # as a _ColdStartRetry: it must NOT stop the process (it is healthy and
        # will be reused) and must NOT consume the fatal retry budget. The next
        # attempt re-attaches to the same live process; once it has finished
        # cold start the handshake succeeds and stays healthy.
        try:
            transport = await self.owner.exit_stack.enter_async_context(websocket_client(websocket_url))
            read_stream, write_stream = transport
            self.owner.session = await self.owner.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.RELAY_CONNECT
            if not await self._managed_process_has_exited():
                # Process is alive but not yet serving (cold start) — reconnect.
                raise _ColdStartRetry(f'{self.server_name}: transport not ready during cold start')
            raise

        try:
            await asyncio.wait_for(self.owner.session.initialize(), timeout=_HANDSHAKE_ATTEMPT_TIMEOUT_SEC)
        except Exception as exc:
            self.owner.error_phase = MCPSessionErrorPhase.MCP_INIT
            if not await self._managed_process_has_exited():
                raise _ColdStartRetry(
                    f'{self.server_name}: handshake not ready during cold start ({type(exc).__name__})'
                )
            raise

    async def monitor_process_health(self) -> None:
        from langbot_plugin.box.models import BoxManagedProcessStatus

        workspace = self._build_workspace()
        consecutive_errors = 0
        while not self.owner._shutdown_event.is_set():
            try:
                info = await workspace.get_managed_process(self.process_id)
                if isinstance(info, dict):
                    status = info.get('status', '')
                else:
                    status = getattr(info, 'status', '')
                if status == BoxManagedProcessStatus.EXITED.value or status == BoxManagedProcessStatus.EXITED:
                    return
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                self.ap.logger.warning(
                    f'MCP monitor for {self.server_name}: get_managed_process failed '
                    f'({consecutive_errors}/{self.owner._MONITOR_MAX_CONSECUTIVE_ERRORS}): '
                    f'{type(exc).__name__}: {exc}'
                )
                if consecutive_errors >= self.owner._MONITOR_MAX_CONSECUTIVE_ERRORS:
                    return

            # Capture stderr logs from the managed process
            if isinstance(info, dict):
                stderr_text = info.get('stderr', '') or info.get('stderr_preview', '')
            else:
                stderr_text = getattr(info, 'stderr', '') or getattr(info, 'stderr_preview', '')

            if stderr_text and stderr_text != self.owner._last_stderr_text:
                # Find new lines not in the previous snapshot
                old_lines = set(self.owner._last_stderr_text.splitlines()) if self.owner._last_stderr_text else set()
                new_lines = [l for l in stderr_text.splitlines() if l and l not in old_lines]
                self.owner._last_stderr_text = stderr_text

                import time as _time

                for line in new_lines:
                    level = (
                        'error'
                        if any(k in line.upper() for k in ('ERROR', 'CRITICAL'))
                        else 'warning'
                        if 'WARNING' in line.upper()
                        else 'debug'
                        if 'DEBUG' in line.upper()
                        else 'info'
                    )
                    self.owner._log_buffer.append({'ts': _time.time(), 'level': level, 'text': line})

            await asyncio.sleep(self.owner._MONITOR_POLL_INTERVAL)

    async def _managed_process_is_running(self) -> bool:
        """Return True if this server's managed process exists and is running.

        Used to decide whether initialize() must (re)start the process or can
        simply re-attach the WebSocket transport to a process the Box runtime
        kept alive across a transient transport drop.
        """
        from langbot_plugin.box.models import BoxManagedProcessStatus

        workspace = self._build_workspace()
        try:
            info = await workspace.get_managed_process(self.process_id)
        except Exception:
            return False
        status = info.get('status', '') if isinstance(info, dict) else getattr(info, 'status', '')
        return status in (BoxManagedProcessStatus.RUNNING.value, BoxManagedProcessStatus.RUNNING)

    async def _managed_process_has_exited(self) -> bool:
        """Return True only if the process is DEFINITIVELY gone (reports EXITED).

        Distinct from ``not _managed_process_is_running()``: a process that has
        just been spawned may not yet report RUNNING, and a transient query
        error is not proof of exit. During the cold-start handshake retry we
        must NOT treat 'not yet running' or 'query failed' as a terminal
        failure, or we bail out to the outer rebuild path and churn the
        process (relay then rejects the early re-attach with HTTP 400). Only a
        successful query that reports EXITED stops the retry loop.
        """
        from langbot_plugin.box.models import BoxManagedProcessStatus

        workspace = self._build_workspace()
        try:
            info = await workspace.get_managed_process(self.process_id)
        except Exception:
            # Unknown — treat as 'still coming up', not exited.
            return False
        status = info.get('status', '') if isinstance(info, dict) else getattr(info, 'status', '')
        return status in (BoxManagedProcessStatus.EXITED.value, BoxManagedProcessStatus.EXITED)

    async def _stage_host_path_to_shared_workspace(self, host_path: str) -> str:
        source_path = normalize_host_path(host_path)
        if not source_path:
            return '/workspace'
        if not os.path.isdir(source_path):
            raise FileNotFoundError(f'MCP host_path does not exist or is not a directory: {host_path}')

        self._validate_host_path(source_path)

        shared_host_path = self._shared_workspace_host_path()
        process_host_root = os.path.join(shared_host_path, '.mcp', self.process_id)
        process_host_workspace = os.path.join(process_host_root, 'workspace')
        await asyncio.to_thread(self._copy_workspace_tree, source_path, process_host_root, process_host_workspace)
        return f'/workspace/.mcp/{self.process_id}/workspace'

    def _validate_host_path(self, host_path: str) -> None:
        self.ap.box_service.build_spec(
            {
                'session_id': f'mcp-validate-{self.process_id}',
                'host_path': host_path,
                'host_path_mode': self.config.host_path_mode,
                'network': self.config.network,
                'read_only_rootfs': self.config.read_only_rootfs if self.config.read_only_rootfs is not None else False,
            }
        )

    def _shared_workspace_host_path(self) -> str:
        default_workspace = getattr(self.ap.box_service, 'default_workspace', None)
        if not default_workspace:
            raise RuntimeError('Box default workspace is required for shared MCP host_path staging')
        shared_host_path = normalize_host_path(default_workspace)
        os.makedirs(shared_host_path, exist_ok=True)
        return shared_host_path

    @staticmethod
    def _copy_workspace_tree(source_path: str, process_host_root: str, process_host_workspace: str) -> None:
        # Docker-backed bootstrap writes root-owned runtime directories such as
        # .venv/.tmp into the staged workspace. The host process may not be able
        # to delete them, so refresh source files in place and preserve runtime
        # directories instead of rmtree'ing the whole staging root.
        with _workspace_copy_lock(process_host_root):
            preserved_names = {'.venv', 'venv', 'env', '.cache', '.tmp', '.langbot'}
            os.makedirs(process_host_workspace, exist_ok=True)
            for name in os.listdir(process_host_workspace):
                if name in preserved_names:
                    continue
                path = os.path.join(process_host_workspace, name)
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    # The entry may disappear between listdir and unlink if cleanup races us.
                    with suppress(FileNotFoundError):
                        os.unlink(path)
            shutil.copytree(
                source_path,
                process_host_workspace,
                symlinks=True,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    '.git',
                    '__pycache__',
                    '.pytest_cache',
                    '.mypy_cache',
                    '.ruff_cache',
                    '.venv',
                    'venv',
                    'env',
                    '.cache',
                    '.tmp',
                    '.langbot',
                ),
            )

    async def _cleanup_staged_workspace(self) -> None:
        if not self.resolve_host_path():
            return
        try:
            process_host_root = os.path.join(self._shared_workspace_host_path(), '.mcp', self.process_id)
            await asyncio.to_thread(shutil.rmtree, process_host_root, True)
        except Exception as exc:
            self.ap.logger.warning(
                f'MCP server {self.server_name}: failed to clean staged workspace '
                f'process_id={self.process_id}: {type(exc).__name__}: {exc}'
            )

    async def _wait_for_box_runtime(self) -> None:
        timeout_sec = max(float(self.config.startup_timeout_sec or 120), 1.0)
        deadline = asyncio.get_running_loop().time() + timeout_sec
        warned = False
        while not getattr(self.ap.box_service, 'available', False):
            if not warned:
                self.ap.logger.warning(
                    f'MCP server {self.server_name}: waiting for Box runtime before starting stdio process'
                )
                warned = True
            if asyncio.get_running_loop().time() >= deadline:
                self.owner.error_phase = MCPSessionErrorPhase.SESSION_CREATE
                raise Exception(f'Box runtime is not available after {int(timeout_sec)} seconds')
            await asyncio.sleep(1)

    async def cleanup_session(self) -> None:
        if not self.uses_box_stdio():
            return

        workspace = self._build_workspace(host_path=None)

        # Transient config-page tests now share the same 'mcp-shared' Box
        # session as live servers, so we must NOT tear the session down here —
        # that would kill every other MCP server in the container. A test is
        # isolated at the process level: it ran under its own process_id, so we
        # stop only that process, exactly like a live server does below. The
        # shared session and all other servers' live processes are untouched.
        # (Staged per-test workspace files are still cleaned up.)
        if getattr(self.owner, 'is_transient', False):
            try:
                await workspace.stop_managed_process(self.process_id)
            except Exception as exc:
                self.ap.logger.warning(
                    f'MCP server {self.server_name}: failed to stop transient test process '
                    f'process_id={self.process_id}: {type(exc).__name__}: {exc}'
                )
            await self._cleanup_staged_workspace()
            return

        # In the shared-session model, we do not delete the session itself.
        # Stop only this MCP server's managed process; deleting the session
        # would kill other MCP servers sharing the same container.
        try:
            await workspace.stop_managed_process(self.process_id)
        except Exception as exc:
            self.ap.logger.warning(
                f'MCP server {self.server_name}: failed to stop managed process '
                f'process_id={self.process_id}: {type(exc).__name__}: {exc}'
            )
            await self._cleanup_staged_workspace()
            return
        await self._cleanup_staged_workspace()
        self.ap.logger.info(
            f'MCP server {self.server_name}: stopped process_id={self.process_id} '
            f'(shared session {self.owner._build_box_session_id()} kept alive)'
        )

    def rewrite_path(self, path: str, host_path: str | None) -> str:
        return rewrite_mounted_path(path, host_path)

    def infer_host_path(self) -> str | None:
        return infer_workspace_host_path(self.server_config.get('command', ''), self.server_config.get('args', []))

    @staticmethod
    def unwrap_venv_path(directory: str) -> str:
        return unwrap_venv_path(directory)

    def resolve_host_path(self) -> str | None:
        return self.config.host_path or self.infer_host_path()

    @staticmethod
    def detect_install_command(host_path: str, workspace_path: str = '/workspace') -> str | None:
        workspace_kind = classify_python_workspace(host_path)
        if workspace_kind in {'package', 'requirements'}:
            return wrap_python_command_with_env('python -c "pass"', mount_path=workspace_path).rstrip()
        return None

    @staticmethod
    def _wrap_process_payload_with_python_env(payload: dict[str, Any], workspace_path: str) -> dict[str, Any]:
        """Start a prepared Python workspace without writing bootstrap output to MCP stdio."""
        workspace_root = workspace_path.rstrip('/') or '/workspace'
        venv_dir = f'{workspace_root}/.venv'
        venv_bin = f'{venv_dir}/bin'
        command = ' '.join([shlex.quote(payload['command']), *[shlex.quote(arg) for arg in payload.get('args', [])]])
        wrapped = dict(payload)
        wrapped['command'] = 'sh'
        wrapped['args'] = [
            '-lc',
            (f'export VIRTUAL_ENV={shlex.quote(venv_dir)}; export PATH={shlex.quote(venv_bin)}:$PATH; exec {command}'),
        ]
        return wrapped

    def build_box_session_payload(self, session_id: str, host_path: str | None = None) -> dict[str, Any]:
        workspace = self._build_workspace()
        workspace.session_id = session_id
        if host_path is not None:
            workspace.host_path = host_path
        return workspace.build_session_payload()

    def build_box_process_payload(self, host_path: str | None = None) -> dict[str, Any]:
        workspace = self._build_workspace()
        if host_path is not None:
            workspace.host_path = host_path
        return workspace.build_process_payload(
            self.server_config['command'],
            self.server_config.get('args', []),
            env=self.server_config.get('env', {}),
        )

    def rewrite_venv_command(self, command: str, host_path: str) -> str:
        return rewrite_venv_command(command, host_path)
