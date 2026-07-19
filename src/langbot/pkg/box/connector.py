from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import typing
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.io.connection import Connection

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import BoxRuntimeUnavailableError
from langbot_plugin.box.actions import LangBotToBoxAction
from langbot_plugin.box.security import (
    BOX_CONTROL_TOKEN_ENV,
    BOX_CONTROL_TOKEN_HEADER,
    BOX_INSTANCE_HEADER,
    BOX_PLACEMENT_GENERATION_HEADER,
    BOX_TRUSTED_INSTANCE_ENV,
    BOX_WORKSPACE_HEADER,
    normalize_instance_uuid,
    validate_control_token,
)
from langbot_plugin.entities.io.context import ActionContext

from ..utils import platform
from ..utils.managed_runtime import ManagedRuntimeConnector

if TYPE_CHECKING:
    from ..core import app as core_app


# Default Docker Compose service name for the standalone Box container.
_DOCKER_BOX_HOST = 'langbot_box'
_DEFAULT_PORT = 5410

_HEARTBEAT_INTERVAL_SEC = 20

# Top-level keys under ``box`` that are LangBot-internal and should not be
# forwarded to the Box runtime.
_INTERNAL_BOX_CONFIG_KEYS = frozenset({'runtime'})


def _get_box_config(ap) -> dict:
    """Return the 'box' section from instance config.

    Environment-variable overrides are handled uniformly by
    ``LoadConfigStage._apply_env_overrides_to_config`` using the
    ``SECTION__SUBSECTION__KEY`` convention (e.g. ``BOX__LOCAL__HOST_ROOT``,
    ``BOX__LOCAL__ALLOWED_MOUNT_ROOTS="/a,/b"``) before this is read, so no
    box-specific env parsing is needed here.
    """
    instance_config = getattr(ap, 'instance_config', None)
    config_data = getattr(instance_config, 'data', {}) if instance_config is not None else {}
    return dict(config_data.get('box', {}) or {})


def _get_runtime_endpoint(box_cfg: dict) -> str:
    runtime_cfg = box_cfg.get('runtime') or {}
    return str(runtime_cfg.get('endpoint', '')).strip()


def _filter_config_for_runtime(box_cfg: dict) -> dict:
    return {k: v for k, v in box_cfg.items() if k not in _INTERNAL_BOX_CONFIG_KEYS}


def resolve_box_ws_relay_url(ap: core_app.Application) -> str:
    """Derive the WS relay base URL used for managed-process attach.

    The WS relay serves the ``/v1/sessions/{id}/managed-process/ws`` endpoint
    on the *relay* port (default 5410).
    """
    box_cfg = _get_box_config(ap)

    # Explicit runtime endpoint takes precedence. The config value is a base
    # URL; endpoint-specific paths are appended by the SDK client.
    endpoint = _get_runtime_endpoint(box_cfg)
    if endpoint:
        parsed = urlparse(endpoint)
        scheme = parsed.scheme or 'ws'
        if scheme == 'ws':
            scheme = 'http'
        elif scheme == 'wss':
            scheme = 'https'
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or _DEFAULT_PORT
        return f'{scheme}://{host}:{port}'

    # In Docker, relay lives on the box runtime container.
    if platform.get_platform() == 'docker':
        return f'http://{_DOCKER_BOX_HOST}:{_DEFAULT_PORT}'

    return f'http://127.0.0.1:{_DEFAULT_PORT}'


class BoxRuntimeConnector(ManagedRuntimeConnector):
    """Connect to the Box runtime via action RPC.

    Transport decision (mirrors Plugin runtime logic):
      1. Docker / --standalone-box / explicit runtime.endpoint -> WebSocket to external Box process
      2. Windows (non-Docker)                              -> subprocess + WebSocket (Windows lacks async stdio pipe)
      3. Unix / macOS                                      -> subprocess + stdio pipe
    """

    def __init__(
        self,
        ap: core_app.Application,
        runtime_disconnect_callback: typing.Callable[
            ['BoxRuntimeConnector'], typing.Coroutine[typing.Any, typing.Any, None]
        ]
        | None = None,
    ):
        super().__init__(ap)
        self.runtime_disconnect_callback = runtime_disconnect_callback
        self.configured_runtime_endpoint = self._load_configured_runtime_endpoint()
        self.ws_relay_base_url = resolve_box_ws_relay_url(ap)
        self.client = ActionRPCBoxClient(logger=ap.logger)

        self._handler: Handler | None = None
        self._handler_task: asyncio.Task | None = None
        self._ctrl_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

        # Parse the relay URL once for reuse.
        parsed = urlparse(self.ws_relay_base_url)
        self._relay_host = parsed.hostname or '127.0.0.1'
        self._relay_port = parsed.port or _DEFAULT_PORT
        self._filtered_box_config = _filter_config_for_runtime(_get_box_config(ap))
        self._trusted_instance_uuid = normalize_instance_uuid(self.ap.workspace_service.instance_uuid)
        self._control_token = str(os.environ.get(BOX_CONTROL_TOKEN_ENV) or '').strip()

    def uses_websocket(self) -> bool:
        """Whether the connector should use WebSocket to reach the Box runtime.

        True when:
          - Running inside Docker (Box runtime is a separate container)
          - The ``--standalone-box`` CLI flag was passed
          - An explicit ``runtime.endpoint`` was configured

        When this is True the Box runtime lives in a separate process with its
        own filesystem view (container, pod sidecar, or remote host), so paths
        it reports (e.g. skill ``package_root``) are NOT resolvable on the
        LangBot side. When False, Box runs as a stdio child process that shares
        LangBot's filesystem.
        """
        return bool(
            self.configured_runtime_endpoint
            or platform.get_platform() == 'docker'
            or platform.use_websocket_to_connect_box_runtime()
        )

    # Backwards-compatible private alias.
    def _uses_websocket(self) -> bool:
        return self.uses_websocket()

    async def initialize(self) -> None:
        if self._uses_websocket():
            if platform.get_platform() == 'win32' and not self.configured_runtime_endpoint:
                await self._start_subprocess_then_ws()
            else:
                await self._connect_remote_ws()
        else:
            await self._start_local_stdio()

        # Start heartbeat after successful connection
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    # -- heartbeat -----------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Periodically ping the Box runtime to detect silent disconnections."""
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_SEC)
            try:
                await self.ping()
                self.ap.logger.debug('Heartbeat to Box runtime success.')
            except Exception as e:
                self.ap.logger.debug(f'Failed to heartbeat to Box runtime: {e}')

    async def ping(self) -> None:
        if self._handler is None:
            raise BoxRuntimeUnavailableError('Box runtime is not connected')
        await self._handler.call_action(CommonAction.PING, {})

    # -- transport paths -----------------------------------------------------

    async def _start_local_stdio(self) -> None:
        """Launch box server as subprocess and connect via stdio (Unix/macOS)."""
        from langbot_plugin.runtime.io.controllers.stdio.client import StdioClientController

        self.ap.logger.info('Use stdio to connect to box runtime')
        self._ensure_control_token(allow_generate=True)
        python_path = sys.executable
        env = os.environ.copy()
        env[BOX_CONTROL_TOKEN_ENV] = self._control_token
        env[BOX_TRUSTED_INSTANCE_ENV] = self._trusted_instance_uuid
        if self._filtered_box_config:
            env['LANGBOT_BOX_CONFIG'] = json.dumps(self._filtered_box_config)

        connected = asyncio.Event()
        connect_error: list[Exception] = []

        ctrl = StdioClientController(
            command=python_path,
            # Launched through the same CLI entry point as the plugin runtime
            # (cli.__init__ <subcommand>); `-s` selects the stdio transport,
            # mirroring `rt -s`.
            args=['-m', 'langbot_plugin.cli.__init__', 'box', '-s', '--ws-control-port', str(self._relay_port)],
            env=env,
        )
        self._ctrl_task = asyncio.create_task(
            ctrl.run(self._make_connection_callback('stdio', connected, connect_error))
        )

        try:
            await asyncio.wait_for(connected.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            raise BoxRuntimeUnavailableError('box runtime subprocess did not connect in time')

        if connect_error:
            raise BoxRuntimeUnavailableError(f'box runtime connection failed: {connect_error[0]}')

        self._subprocess = ctrl.process

    async def _start_subprocess_then_ws(self) -> None:
        """Launch box server as detached subprocess, then connect via WS (Windows)."""
        self.ap.logger.info('(windows) Use cmd to launch box runtime and communicate via ws')

        self._ensure_control_token(allow_generate=True)
        env = os.environ.copy()
        env[BOX_CONTROL_TOKEN_ENV] = self._control_token
        env[BOX_TRUSTED_INSTANCE_ENV] = self._trusted_instance_uuid
        if self._filtered_box_config:
            env['LANGBOT_BOX_CONFIG'] = json.dumps(self._filtered_box_config)

        python_path = sys.executable
        # Launched through the same CLI entry point as the plugin runtime
        # (cli.__init__ <subcommand>); no flag => WebSocket transport.
        self.runtime_subprocess = await asyncio.create_subprocess_exec(
            python_path,
            '-m',
            'langbot_plugin.cli.__init__',
            'box',
            '--ws-control-port',
            str(self._relay_port),
            env=env,
        )
        self.runtime_subprocess_task = asyncio.create_task(self.runtime_subprocess.wait())

        ws_url = f'ws://localhost:{self._relay_port}/rpc/ws'
        await self._connect_ws(ws_url, '(windows) WebSocket')

    async def _connect_remote_ws(self) -> None:
        """Connect to a remote (or Docker) box server via WebSocket."""
        self._ensure_control_token(allow_generate=False)
        ws_url = self._resolve_rpc_ws_url()
        self.ap.logger.info(f'Use WebSocket to connect to box runtime ({ws_url})')
        await self._connect_ws(ws_url, 'WebSocket')

    # -- helpers -------------------------------------------------------------

    def _resolve_rpc_ws_url(self) -> str:
        """Determine the action-RPC WebSocket URL.

        All endpoints share a single port; action RPC is at ``/rpc/ws``.
        """
        if self.configured_runtime_endpoint:
            base = self.configured_runtime_endpoint.rstrip('/')
            parsed = urlparse(base)
            scheme = parsed.scheme or 'ws'
            if scheme in ('http', 'https'):
                scheme = 'wss' if scheme == 'https' else 'ws'
            host = parsed.hostname or '127.0.0.1'
            port = parsed.port or _DEFAULT_PORT
            return f'{scheme}://{host}:{port}/rpc/ws'

        if platform.get_platform() == 'docker':
            return f'ws://{_DOCKER_BOX_HOST}:{_DEFAULT_PORT}/rpc/ws'

        return f'ws://localhost:{self._relay_port}/rpc/ws'

    async def _connect_ws(self, ws_url: str, transport_name: str) -> None:
        """Shared WebSocket connection procedure."""
        from langbot_plugin.runtime.io.controllers.ws.client import WebSocketClientController

        connected = asyncio.Event()
        connect_error: list[Exception] = []

        async def on_connect_failed(ctrl, exc):
            if exc is not None:
                self.ap.logger.error(f'Failed to connect to Box runtime ({ws_url}): {exc}')
            else:
                self.ap.logger.error(f'Failed to connect to Box runtime ({ws_url}), trying to reconnect...')
            connect_error.append(exc or BoxRuntimeUnavailableError('ws connection failed'))
            connected.set()
            if self.runtime_disconnect_callback is not None:
                await self.runtime_disconnect_callback(self)

        ctrl = WebSocketClientController(
            ws_url=ws_url,
            make_connection_failed_callback=on_connect_failed,
            additional_headers=self.get_control_headers(),
        )
        self._ctrl_task = asyncio.create_task(
            ctrl.run(self._make_connection_callback(transport_name, connected, connect_error))
        )

        try:
            await asyncio.wait_for(connected.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            raise BoxRuntimeUnavailableError(f'box runtime ws connection timed out ({ws_url})')

        if connect_error:
            raise BoxRuntimeUnavailableError(f'box runtime connection failed: {connect_error[0]}')

    def _ensure_control_token(self, *, allow_generate: bool) -> str:
        if not self._control_token and allow_generate:
            self._control_token = secrets.token_urlsafe(48)
        try:
            self._control_token = validate_control_token(self._control_token)
        except ValueError as exc:
            raise BoxRuntimeUnavailableError(
                f'{BOX_CONTROL_TOKEN_ENV} must be configured with a strong shared secret for an external Box runtime'
            ) from exc
        return self._control_token

    def get_control_headers(self) -> dict[str, str]:
        """Headers for the instance-authenticated RPC control handshake."""

        self._ensure_control_token(allow_generate=False)
        return {
            BOX_CONTROL_TOKEN_HEADER: self._control_token,
            BOX_INSTANCE_HEADER: self._trusted_instance_uuid,
        }

    def get_relay_headers(
        self,
        action_context: ActionContext,
    ) -> dict[str, str]:
        """Return authenticated, placement-scoped relay handshake headers."""

        context = ActionContext.model_validate(action_context).without_installation()
        if context.instance_uuid != self._trusted_instance_uuid:
            raise BoxRuntimeUnavailableError('Box relay context belongs to another LangBot instance')
        return {
            **self.get_control_headers(),
            BOX_WORKSPACE_HEADER: context.workspace_uuid,
            BOX_PLACEMENT_GENERATION_HEADER: str(context.placement_generation),
        }

    def _make_connection_callback(
        self,
        transport_name: str,
        connected: asyncio.Event,
        connect_error: list[Exception],
    ):
        async def new_connection_callback(connection: Connection) -> None:
            handler = Handler(connection)
            self._handler = handler
            self.client.set_handler(handler)
            self._handler_task = asyncio.create_task(handler.run())
            try:
                await handler.call_action(CommonAction.PING, {})
                if self._filtered_box_config:
                    await handler.call_action(LangBotToBoxAction.INIT, self._filtered_box_config)
                    self.ap.logger.debug('Sent box configuration to Box runtime via INIT.')
                self.ap.logger.info(f'Connected to Box runtime via {transport_name}.')
                connected.set()
                await self._handler_task
            except Exception as exc:
                if not connected.is_set():
                    connect_error.append(exc)
                    connected.set()
                    return

            # If we reach here, handler.run() returned normally (connection
            # closed) or raised after the initial handshake succeeded.
            # Either way, treat it as a disconnect.
            if connected.is_set():
                if self._uses_websocket():
                    self.ap.logger.error('Disconnected from Box runtime, trying to reconnect...')
                    if self.runtime_disconnect_callback is not None:
                        await self.runtime_disconnect_callback(self)
                else:
                    self.ap.logger.error(
                        'Disconnected from Box runtime via stdio. '
                        'Cannot automatically reconnect — please restart LangBot.'
                    )

        return new_connection_callback

    # -- lifecycle -----------------------------------------------------------

    def dispose(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._handler_task is not None:
            self._handler_task.cancel()
            self._handler_task = None

        if self._ctrl_task is not None:
            self._ctrl_task.cancel()
            self._ctrl_task = None

        # stdio-managed subprocess (stored as self._subprocess by _start_local_stdio)
        if hasattr(self, '_subprocess') and self._subprocess is not None and self._subprocess.returncode is None:
            self.ap.logger.info('Terminating managed box runtime process...')
            self._subprocess.terminate()

        # Subprocess launched by ManagedRuntimeConnector._start_runtime_subprocess (Windows path)
        self._dispose_subprocess()

    # -- config helpers ------------------------------------------------------

    def _load_configured_runtime_endpoint(self) -> str:
        return _get_runtime_endpoint(_get_box_config(self.ap))
