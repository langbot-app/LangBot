# For connect to plugin runtime.
from __future__ import annotations

import asyncio
import typing
import os
import sys

from ..core import app
from . import handler
from ..utils import platform
from langbot_plugin.runtime.io.controllers.stdio import client as stdio_client_controller
from langbot_plugin.runtime.io.controllers.ws import client as ws_client_controller
from langbot_plugin.api.entities import events, context
import langbot_plugin.runtime.io.connection as base_connection


class PluginRuntimeConnector:
    """Plugin runtime connector"""

    ap: app.Application

    handler: handler.RuntimeConnectionHandler

    handler_task: asyncio.Task

    stdio_client_controller: stdio_client_controller.StdioClientController

    runtime_disconnect_callback: typing.Callable[
        [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
    ]

    def __init__(
        self,
        ap: app.Application,
        runtime_disconnect_callback: typing.Callable[
            [PluginRuntimeConnector], typing.Coroutine[typing.Any, typing.Any, None]
        ],
    ):
        self.ap = ap
        self.runtime_disconnect_callback = runtime_disconnect_callback

    async def initialize(self):
        async def new_connection_callback(connection: base_connection.Connection):
            async def disconnect_callback(rchandler: handler.RuntimeConnectionHandler) -> bool:
                if platform.get_platform() == 'docker':
                    self.ap.logger.error('Disconnected from plugin runtime, trying to reconnect...')
                    await self.runtime_disconnect_callback(self)
                    return False
                else:
                    self.ap.logger.error(
                        'Disconnected from plugin runtime, cannot automatically reconnect while LangBot connects to plugin runtime via stdio, please restart LangBot.'
                    )
                    return False

            self.handler = handler.RuntimeConnectionHandler(connection, disconnect_callback, self.ap)
            self.handler_task = asyncio.create_task(self.handler.run())
            _ = await self.handler.ping()
            self.ap.logger.info('Connected to plugin runtime.')
            await self.handler_task

        task: asyncio.Task | None = None

        if platform.get_platform() == 'docker':  # use websocket
            self.ap.logger.info('use websocket to connect to plugin runtime')
            ws_url = self.ap.instance_config.data['plugin']['runtime_ws_url']

            async def make_connection_failed_callback(ctrl: ws_client_controller.WebSocketClientController) -> None:
                self.ap.logger.error('Failed to connect to plugin runtime, trying to reconnect...')
                await self.runtime_disconnect_callback(self)

            ctrl = ws_client_controller.WebSocketClientController(
                ws_url=ws_url,
                make_connection_failed_callback=make_connection_failed_callback,
            )
            task = ctrl.run(new_connection_callback)
        else:  # stdio
            self.ap.logger.info('use stdio to connect to plugin runtime')
            # cmd: lbp rt -s
            python_path = sys.executable
            env = os.environ.copy()
            ctrl = stdio_client_controller.StdioClientController(
                command=python_path,
                args=['-m', 'langbot_plugin.cli.__init__', 'rt', '-s'],
                env=env,
            )
            task = ctrl.run(new_connection_callback)

        asyncio.create_task(task)

    async def initialize_plugins(self):
        pass

    async def emit_event(
        self,
        event: events.BaseEventModel,
    ) -> context.EventContext:
        event_ctx = context.EventContext(
            event=event,
        )

        event_ctx_result = await self.handler.emit_event(event_ctx.model_dump(serialize_as_any=True))

        event_ctx = context.EventContext.parse_from_dict(event_ctx_result['event_context'])

        return event_ctx
