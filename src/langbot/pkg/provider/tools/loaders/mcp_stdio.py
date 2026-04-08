from __future__ import annotations

import enum
import os
import asyncio
from typing import TYPE_CHECKING, Any

import pydantic
from mcp import ClientSession
from mcp.client.websocket import websocket_client

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


_VENV_DIRS = frozenset({'.venv', 'venv', 'env', '.env'})
_VENV_BIN_DIRS = frozenset({'bin', 'Scripts'})


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

    def uses_box_stdio(self) -> bool:
        if self.server_config.get('mode') != 'stdio':
            return False
        try:
            return bool(getattr(self.ap.box_service, 'available', False))
        except Exception:
            return False

    async def initialize(self) -> None:
        box_service = self.ap.box_service
        session_id = self.owner._build_box_session_id()
        host_path = self.resolve_host_path()
        session_payload = self.build_box_session_payload(session_id, host_path)

        try:
            await box_service.create_session(session_payload)
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.SESSION_CREATE
            raise

        if host_path:
            install_cmd = self.owner._detect_install_command(host_path)
            if install_cmd:
                self.ap.logger.info(f'MCP server {self.server_name}: installing dependencies in Box with: {install_cmd}')
                exec_payload = dict(session_payload)
                exec_payload['cmd'] = install_cmd
                exec_payload['timeout_sec'] = self.config.startup_timeout_sec or 120
                try:
                    result = await box_service.client.execute(box_service.build_spec(exec_payload))
                except Exception:
                    self.owner.error_phase = MCPSessionErrorPhase.DEP_INSTALL
                    raise
                if not result.ok:
                    self.owner.error_phase = MCPSessionErrorPhase.DEP_INSTALL
                    stderr_preview = (result.stderr or '')[:500]
                    raise Exception(f'Dependency install failed (exit code {result.exit_code}): {stderr_preview}')

        try:
            await box_service.start_managed_process(session_id, self.build_box_process_payload(host_path))
        except Exception:
            self.owner.error_phase = MCPSessionErrorPhase.PROCESS_START
            raise

        try:
            websocket_url = box_service.get_managed_process_websocket_url(session_id)
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

        session_id = self.owner._build_box_session_id()
        consecutive_errors = 0
        while not self.owner._shutdown_event.is_set():
            try:
                info = await self.ap.box_service.get_managed_process(session_id)
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
            await self.ap.box_service.client.delete_session(self.owner._build_box_session_id())
        except Exception as exc:
            self.ap.logger.warning(f'Failed to cleanup Box session for MCP server {self.server_name}: {exc}')

    def rewrite_path(self, path: str, host_path: str | None) -> str:
        if not host_path or not path:
            return path
        normalized_host = os.path.realpath(host_path)
        if path.startswith(normalized_host + '/'):
            return '/workspace' + path[len(normalized_host) :]
        if path == normalized_host:
            return '/workspace'
        return path

    def infer_host_path(self) -> str | None:
        candidates = []
        parts = [self.server_config.get('command', '')] + self.server_config.get('args', [])
        for part in parts:
            if not os.path.isabs(part):
                continue
            if os.path.exists(part):
                directory = os.path.dirname(part)
                directory = self.unwrap_venv_path(directory)
                candidates.append(os.path.realpath(directory))
        if not candidates:
            return None
        common = os.path.commonpath(candidates)
        return common if common != '/' else None

    @staticmethod
    def unwrap_venv_path(directory: str) -> str:
        parts = directory.replace('\\', '/').split('/')
        for i in range(len(parts) - 1, 0, -1):
            if parts[i] in _VENV_BIN_DIRS and i >= 1:
                venv_dir = parts[i - 1]
                if venv_dir in _VENV_DIRS:
                    project_root = '/'.join(parts[: i - 1])
                    return project_root if project_root else '/'
        return directory

    def resolve_host_path(self) -> str | None:
        return self.config.host_path or self.infer_host_path()

    @staticmethod
    def detect_install_command(host_path: str) -> str | None:
        copy_and_install = (
            'mkdir -p /opt/_mcp_src'
            ' && tar -C /workspace'
            ' --exclude=.venv --exclude=.git --exclude=__pycache__'
            ' --exclude=node_modules --exclude=.tox --exclude=.nox'
            ' --exclude="*.egg-info" --exclude=.uv-cache'
            ' -cf - .'
            ' | tar -C /opt/_mcp_src -xf -'
            ' && pip install --no-cache-dir /opt/_mcp_src'
            ' && rm -rf /opt/_mcp_src'
        )
        install_requirements = 'pip install --no-cache-dir -r /workspace/requirements.txt'

        if os.path.isfile(os.path.join(host_path, 'pyproject.toml')):
            return copy_and_install
        if os.path.isfile(os.path.join(host_path, 'setup.py')):
            return copy_and_install
        if os.path.isfile(os.path.join(host_path, 'requirements.txt')):
            return install_requirements
        return None

    def build_box_session_payload(self, session_id: str, host_path: str | None = None) -> dict[str, Any]:
        if host_path is None:
            host_path = self.resolve_host_path()

        payload: dict[str, Any] = {
            'session_id': session_id,
            'workdir': '/workspace',
            'env': self.config.env,
            'network': self.config.network,
            'read_only_rootfs': self.config.read_only_rootfs if self.config.read_only_rootfs is not None else False,
        }
        if host_path:
            payload['host_path'] = host_path
            payload['host_path_mode'] = self.config.host_path_mode
        for key in ('image', 'cpus', 'memory_mb', 'pids_limit'):
            value = getattr(self.config, key)
            if value is not None:
                payload[key] = value if not isinstance(value, enum.Enum) else value.value
        return payload

    def build_box_process_payload(self, host_path: str | None = None) -> dict[str, Any]:
        if host_path is None:
            host_path = self.resolve_host_path()

        command = self.server_config['command']
        args = self.server_config.get('args', [])
        cwd = '/workspace'

        if host_path:
            command = self.rewrite_venv_command(command, host_path)
            args = [self.rewrite_path(arg, host_path) for arg in args]
            cwd = self.rewrite_path(cwd, host_path)

        return {
            'command': command,
            'args': args,
            'env': self.server_config.get('env', {}),
            'cwd': cwd,
        }

    def rewrite_venv_command(self, command: str, host_path: str) -> str:
        if not host_path or not command:
            return command
        normalized_host = os.path.realpath(host_path)
        if not command.startswith(normalized_host + '/'):
            return command
        rel = command[len(normalized_host) + 1 :]
        parts = rel.replace('\\', '/').split('/')
        if len(parts) >= 3 and parts[0] in _VENV_DIRS and parts[1] in _VENV_BIN_DIRS and parts[2].startswith('python'):
            return 'python'
        return self.rewrite_path(command, host_path)
