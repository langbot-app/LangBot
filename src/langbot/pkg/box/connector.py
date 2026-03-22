from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.io.connection import Connection

from .client import ActionRPCBoxClient, resolve_box_ws_relay_url
from .errors import BoxRuntimeUnavailableError
from .models import get_box_config
from ..utils import platform

if TYPE_CHECKING:
    from ..core import app as core_app


class BoxRuntimeConnector:
    """Connect to the Box runtime via action RPC (stdio or ws)."""

    def __init__(self, ap: 'core_app.Application'):
        self.ap = ap
        self.configured_runtime_url = self._load_configured_runtime_url()
        self.manages_local_runtime = self._should_manage_local_runtime()
        self.ws_relay_base_url = resolve_box_ws_relay_url(ap)
        self.client = ActionRPCBoxClient(logger=ap.logger)

        self._handler: Handler | None = None
        self._handler_task: asyncio.Task | None = None
        self._ctrl_task: asyncio.Task | None = None
        self._subprocess: asyncio.subprocess.Process | None = None

        # Parse the relay URL once for reuse
        parsed = urlparse(self.ws_relay_base_url)
        self._relay_host = parsed.hostname or '127.0.0.1'
        self._relay_port = parsed.port or 5410

    async def initialize(self) -> None:
        if self.manages_local_runtime:
            await self._start_local_stdio()
        else:
            await self._connect_remote_ws()

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

        return new_connection_callback

    async def _start_local_stdio(self) -> None:
        """Launch box server as subprocess and connect via stdio."""
        from langbot_plugin.runtime.io.controllers.stdio.client import StdioClientController

        python_path = sys.executable
        env = os.environ.copy()

        connected = asyncio.Event()
        connect_error: list[Exception] = []

        ctrl = StdioClientController(
            command=python_path,
            args=['-m', 'langbot.pkg.box.server', '--port', str(self._relay_port)],
            env=env,
        )
        self._subprocess = None  # StdioClientController manages the subprocess
        self._ctrl_task = asyncio.create_task(
            ctrl.run(self._make_connection_callback('stdio', connected, connect_error))
        )

        # Wait for connection or failure
        try:
            await asyncio.wait_for(connected.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            raise BoxRuntimeUnavailableError('box runtime subprocess did not connect in time')

        if connect_error:
            raise BoxRuntimeUnavailableError(f'box runtime connection failed: {connect_error[0]}')

        # Store subprocess reference for dispose
        self._subprocess = ctrl.process

    async def _connect_remote_ws(self) -> None:
        """Connect to a remote box server via WebSocket."""
        from langbot_plugin.runtime.io.controllers.ws.client import WebSocketClientController

        ws_url = f'ws://{self._relay_host}:{self._relay_port + 1}'

        connected = asyncio.Event()
        connect_error: list[Exception] = []

        async def on_connect_failed(ctrl, exc):
            connect_error.append(exc or BoxRuntimeUnavailableError('ws connection failed'))
            connected.set()

        ctrl = WebSocketClientController(ws_url=ws_url, make_connection_failed_callback=on_connect_failed)
        self._ctrl_task = asyncio.create_task(
            ctrl.run(self._make_connection_callback('WebSocket', connected, connect_error))
        )

        try:
            await asyncio.wait_for(connected.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            raise BoxRuntimeUnavailableError('box runtime ws connection timed out')

        if connect_error:
            raise BoxRuntimeUnavailableError(f'box runtime connection failed: {connect_error[0]}')

    def dispose(self) -> None:
        if self._handler_task is not None:
            self._handler_task.cancel()
            self._handler_task = None

        if self._ctrl_task is not None:
            self._ctrl_task.cancel()
            self._ctrl_task = None

        if self._subprocess is not None and self._subprocess.returncode is None:
            self.ap.logger.info('Terminating managed box runtime process...')
            self._subprocess.terminate()

    def _load_configured_runtime_url(self) -> str:
        return str(get_box_config(self.ap).get('runtime_url', '')).strip()

    def _should_manage_local_runtime(self) -> bool:
        return not self.configured_runtime_url and platform.get_platform() != 'docker'
