from __future__ import annotations

import enum
import asyncio
import os
import shutil
import shlex
import threading
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
            memory_mb=self.config.memory_mb,
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

        try:
            websocket_url = workspace.get_managed_process_websocket_url(self.process_id)
            transport = await self.owner.exit_stack.enter_async_context(websocket_client(websocket_url))
            read_stream, write_stream = transport
            self.owner.session = await self.owner.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.RELAY_CONNECT
            raise

        try:
            await self.owner.session.initialize()
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.MCP_INIT
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
            await asyncio.sleep(self.owner._MONITOR_POLL_INTERVAL)

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
            preserved_names = {'.venv', 'venv', 'env', '.env', '.cache', '.tmp', '.langbot'}
            os.makedirs(process_host_workspace, exist_ok=True)
            for name in os.listdir(process_host_workspace):
                if name in preserved_names:
                    continue
                path = os.path.join(process_host_workspace, name)
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    try:
                        os.unlink(path)
                    except FileNotFoundError:
                        pass
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
                    '.env',
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

        # Transient test sessions own their isolated Box session, so tear the
        # whole session down rather than leaking it. This cannot affect live
        # servers because they live in the separate shared session.
        if getattr(self.owner, 'is_transient', False):
            try:
                await workspace.cleanup()
            except Exception as exc:
                self.ap.logger.warning(
                    f'MCP server {self.server_name}: failed to delete transient test session '
                    f'{self.owner._build_box_session_id()}: {type(exc).__name__}: {exc}'
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
        command = ' '.join(
            [shlex.quote(payload['command']), *[shlex.quote(arg) for arg in payload.get('args', [])]]
        )
        wrapped = dict(payload)
        wrapped['command'] = 'sh'
        wrapped['args'] = [
            '-lc',
            (
                f'export VIRTUAL_ENV={shlex.quote(venv_dir)}; '
                f'export PATH={shlex.quote(venv_bin)}:$PATH; '
                f'exec {command}'
            ),
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
