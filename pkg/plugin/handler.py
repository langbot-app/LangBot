from __future__ import annotations

import typing
from typing import Any

import sqlalchemy

from langbot_plugin.runtime.io import handler
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    RuntimeToLangBotAction,
    LangBotToRuntimeAction,
)

from ..entity.persistence import plugin as persistence_plugin

from ..core import app


class RuntimeConnectionHandler(handler.Handler):
    """Runtime connection handler"""

    ap: app.Application

    def __init__(
        self,
        connection: Connection,
        disconnect_callback: typing.Callable[[], typing.Coroutine[typing.Any, typing.Any, bool]],
        ap: app.Application,
    ):
        super().__init__(connection, disconnect_callback)
        self.ap = ap

        @self.action(RuntimeToLangBotAction.GET_PLUGIN_SETTINGS)
        async def get_plugin_settings(data: dict[str, Any]) -> handler.ActionResponse:
            """Get plugin settings"""

            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_plugin.PluginSetting)
                .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
            )

            data = {
                'enabled': False,
                'priority': 0,
                'plugin_config': {},
            }

            setting = result.first()

            if setting is not None:
                data['enabled'] = setting.enabled
                data['priority'] = setting.priority
                data['plugin_config'] = setting.config

            return handler.ActionResponse.success(
                data=data,
            )

    async def ping(self) -> dict[str, Any]:
        """Ping the runtime"""
        return await self.call_action(
            CommonAction.PING,
            {},
            timeout=10,
        )

    async def list_plugins(self) -> list[dict[str, Any]]:
        """List plugins"""
        result = await self.call_action(
            LangBotToRuntimeAction.LIST_PLUGINS,
            {},
            timeout=10,
        )

        return result['plugins']

    async def emit_event(
        self,
        event_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Emit event"""
        result = await self.call_action(
            LangBotToRuntimeAction.EMIT_EVENT,
            {
                'event_context': event_context,
            },
            timeout=10,
        )

        return result
