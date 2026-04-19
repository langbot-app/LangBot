from __future__ import annotations

import asyncio
import os
import sys
import typing
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.io.connection import Connection

from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import BoxRuntimeUnavailableError

from ..utils import platform
from ..utils.managed_runtime import ManagedRuntimeConnector

if TYPE_CHECKING:
    from ..core import app as core_app


# Default Docker Compose service name for the standalone Box container.
_DOCKER_BOX_HOST = 'langbot_box'
_DEFAULT_PORT = 5410

_HEARTBEAT_INTERVAL_SEC = 20


def _get_box_config(ap) -> dict:
    """Return the 'box' section from instance config, with safe fallbacks."""
    instance_config = getattr(ap, 'instance_config', None)
    config_data = getattr(instance_config, 'data', {}) if instance_config is not None else {}
    return config_data.get('box', {})


def resolve_box_ws_relay_url(ap: core_app.Application) -> str:
    """Derive the WS relay base URL used for managed-process attach.

    The WS relay serves the ``/v1/sessions/{id}/managed-process/ws`` endpoint
    on the *relay* port (default 5410).
    """
    box_cfg = _get_box_config(ap)

    # Explicit relay URL takes precedence.
    runtime_url = str(box_cfg.get('runtime_url', '')).strip()
    if runtime_url:
        return runtime_url

    # In Docker, relay lives on the box runtime container.
    if platform.get_platform() == 'docker':
        return f'http://{_DOCKER_BOX_HOST}:{_DEFAULT_PORT}'

    return f'http://127.0.0.1:{_DEFAULT_PORT}'


class BoxRuntimeConnector(ManagedRuntimeConnector):
    """Connect to the Box runtime via action RPC.

    Transport decision (mirrors Plugin runtime logic):
      1. Docker / --standalone-box / explicit runtime_url  -> WebSocket to external Box process
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
        self.configured_runtime_url = self._load_configured_runtime_url()
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

    def _uses_websocket(self) -> bool:
        """Whether the connector should use WebSocket to reach the Box runtime.

        True when:
          - Running inside Docker (Box runtime is a separate container)
          - The ``--standalone-box`` CLI flag was passed
          - An explicit ``runtime_url`` was configured
        """
        return bool(
            self.configured_runtime_url
            or platform.get_platform() == 'docker'
            or platform.use_websocket_to_connect_box_runtime()
        )

    async def initialize(self) -> None:
        if self._uses_websocket():
            if platform.get_platform() == 'win32' and not self.configured_runtime_url:
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
        python_path = sys.executable
        env = os.environ.copy()

        connected = asyncio.Event()
        connect_error: list[Exception] = []

        ctrl = StdioClientController(
            command=python_path,
            args=['-m', 'langbot_plugin.box.server', '--port', str(self._relay_port)],
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

        await self._start_runtime_subprocess(
            '-m',
            'langbot_plugin.box.server',
            '--mode',
            'ws',
            '--port',
            str(self._relay_port),
        )

        ws_url = f'ws://localhost:{self._relay_port}/rpc/ws'
        await self._connect_ws(ws_url, '(windows) WebSocket')

    async def _connect_remote_ws(self) -> None:
        """Connect to a remote (or Docker) box server via WebSocket."""
        ws_url = self._resolve_rpc_ws_url()
        self.ap.logger.info(f'Use WebSocket to connect to box runtime ({ws_url})')
        await self._connect_ws(ws_url, 'WebSocket')

    # -- helpers -------------------------------------------------------------

    def _resolve_rpc_ws_url(self) -> str:
        """Determine the action-RPC WebSocket URL.

        All endpoints share a single port; action RPC is at ``/rpc/ws``.
        """
        if self.configured_runtime_url:
            return self.configured_runtime_url

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

        ctrl = WebSocketClientController(ws_url=ws_url, make_connection_failed_callback=on_connect_failed)
        self._ctrl_task = asyncio.create_task(
            ctrl.run(self._make_connection_callback(transport_name, connected, connect_error))
        )

        try:
            await asyncio.wait_for(connected.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            raise BoxRuntimeUnavailableError(f'box runtime ws connection timed out ({ws_url})')

        if connect_error:
            raise BoxRuntimeUnavailableError(f'box runtime connection failed: {connect_error[0]}')

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

    def _load_configured_runtime_url(self) -> str:
        return str(_get_box_config(self.ap).get('runtime_url', '')).strip()
