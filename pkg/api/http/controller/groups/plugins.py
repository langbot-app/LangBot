from __future__ import annotations


import traceback

import quart

from .....core import app
from .. import group


@group.group_class('plugins', '/api/v1/plugins')
class PluginsRouterGroup(group.RouterGroup):

    async def initialize(self) -> None:
        @self.route('', methods=['GET'])
        async def _() -> str:
            plugins = self.ap.plugin_mgr.plugins

            plugins_data = [plugin.model_dump() for plugin in plugins]

            return self.success(data={
                'plugins': plugins_data
            })
        
        @self.route('/toggle/<author>/<plugin_name>', methods=['PUT'])
        async def _(author: str, plugin_name: str) -> str:
            data = await quart.request.json
            target_enabled = data.get('target_enabled')
            await self.ap.plugin_mgr.update_plugin_status(plugin_name, target_enabled)
            return self.success()
