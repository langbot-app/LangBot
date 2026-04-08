from __future__ import annotations

import enum
import asyncio
from typing import TYPE_CHECKING, Any

import pydantic
from mcp import ClientSession
from mcp.client.websocket import websocket_client
from ....box.workspace import (
    BoxWorkspaceSession,
    classify_python_workspace,
    infer_workspace_host_path,
    rewrite_mounted_path,
    rewrite_venv_command,
    unwrap_venv_path,
)

if TYPE_CHECKING:
    from .mcp import RuntimeMCPSession


class MCPSessionErrorPhase(enum.Enum):
    """Which phase of the MCP lifecycle failed."""

    SESSION_CREATE = 'session_create'
    DEP_INSTALL = 'dep_install'
    PROCESS_START = 'process_start'
    RELAY_CONNECT = 'relay_connect'
    MCP_INIT = 'mcp_init'
    RUNTIME = 'runtime'
    TOOL_CALL = 'tool_call'


class MCPServerBoxConfig(pydantic.BaseModel):
    """Structured configuration for running an MCP server inside a Box container."""

    image: str | None = None
    network: str = 'on'  # MCP servers need network for dependency installation
    host_path: str | None = None
    host_path_mode: str = 'ro'  # MCP servers default to read-write mount only when explicitly requested
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    startup_timeout_sec: int = 120  # Longer default to allow dependency bootstrap
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

    def _build_workspace(self) -> BoxWorkspaceSession:
        return BoxWorkspaceSession(
            self.ap.box_service,
            self.owner._build_box_session_id(),
            host_path=self.resolve_host_path(),
            host_path_mode=self.config.host_path_mode,
            env=self.config.env,
            network=self.config.network,
            read_only_rootfs=self.config.read_only_rootfs if self.config.read_only_rootfs is not None else False,
            image=self.config.image,
            cpus=self.config.cpus,
            memory_mb=self.config.memory_mb,
            pids_limit=self.config.pids_limit,
        )

    def uses_box_stdio(self) -> bool:
        if self.server_config.get('mode') != 'stdio':
            return False
        try:
            return bool(getattr(self.ap.box_service, 'available', False))
        except Exception:
            return False

    async def initialize(self) -> None:
        workspace = self._build_workspace()
        host_path = workspace.host_path

        try:
            await workspace.create_session()
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.SESSION_CREATE
            raise

        if host_path:
            install_cmd = self.owner._detect_install_command(host_path)
            if install_cmd:
                self.ap.logger.info(f'MCP server {self.server_name}: installing dependencies in Box with: {install_cmd}')
                try:
                    result = await workspace.execute_raw(
                        install_cmd,
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
            await workspace.start_managed_process(
                self.server_config['command'],
                self.server_config.get('args', []),
                env=self.server_config.get('env', {}),
            )
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.PROCESS_START
            raise

        try:
            websocket_url = workspace.get_managed_process_websocket_url()
            transport = await self.owner.exit_stack.enter_async_context(websocket_client(websocket_url))
            read_stream, write_stream = transport
            self.owner.session = await self.owner.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
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
                info = await workspace.get_managed_process()
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

    async def cleanup_session(self) -> None:
        if not self.uses_box_stdio():
            return

        try:
            await self._build_workspace().cleanup()
        except Exception as exc:
            self.ap.logger.warning(f'Failed to cleanup Box session for MCP server {self.server_name}: {exc}')

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
    def detect_install_command(host_path: str) -> str | None:
        workspace_kind = classify_python_workspace(host_path)
        if workspace_kind == 'package':
            return (
                'mkdir -p /opt/_lb_src'
                ' && tar -C /workspace'
                ' --exclude=.venv --exclude=.git --exclude=__pycache__'
                ' --exclude=node_modules --exclude=.tox --exclude=.nox'
                ' --exclude="*.egg-info" --exclude=.uv-cache'
                ' -cf - .'
                ' | tar -C /opt/_lb_src -xf -'
                ' && pip install --no-cache-dir /opt/_lb_src'
                ' && rm -rf /opt/_lb_src'
            )
        if workspace_kind == 'requirements':
            return 'pip install --no-cache-dir -r /workspace/requirements.txt'
        return None

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
