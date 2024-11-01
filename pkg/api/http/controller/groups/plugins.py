from __future__ import annotations


import traceback

import quart

from .....core import app, taskmgr
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
        
        @self.route('/<author>/<plugin_name>/toggle', methods=['PUT'])
        async def _(author: str, plugin_name: str) -> str:
            data = await quart.request.json
            target_enabled = data.get('target_enabled')
            await self.ap.plugin_mgr.update_plugin_status(plugin_name, target_enabled)
            return self.success()
        
        @self.route('/<author>/<plugin_name>/update', methods=['POST'])
        async def _(author: str, plugin_name: str) -> str:
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_mgr.update_plugin(plugin_name, task_context=ctx),
                kind="plugin-operation",
                name=f"plugin-update-{plugin_name}",
                label=f"更新插件 {plugin_name}",
                context=ctx
            )
            return self.success(data={
                'task_id': wrapper.id
            })

        @self.route('/reorder', methods=['PUT'])
        async def _() -> str:
            data = await quart.request.json
            await self.ap.plugin_mgr.reorder_plugins(data.get('plugins'))
            return self.success()
