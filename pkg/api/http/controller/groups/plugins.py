from __future__ import annotations

import base64
import quart

from .....core import taskmgr
from .. import group
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource


@group.group_class('plugins', '/api/v1/plugins')
class PluginsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            plugins = await self.ap.plugin_connector.list_plugins()

            return self.success(data={'plugins': plugins})

        @self.route(
            '/<author>/<plugin_name>/upgrade',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _(author: str, plugin_name: str) -> str:
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.upgrade_plugin(author, plugin_name, task_context=ctx),
                kind='plugin-operation',
                name=f'plugin-upgrade-{plugin_name}',
                label=f'Upgrading plugin {plugin_name}',
                context=ctx,
            )
            return self.success(data={'task_id': wrapper.id})

        @self.route(
            '/<author>/<plugin_name>',
            methods=['GET', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _(author: str, plugin_name: str) -> str:
            if quart.request.method == 'GET':
                plugin = await self.ap.plugin_connector.get_plugin_info(author, plugin_name)
                if plugin is None:
                    return self.http_status(404, -1, 'plugin not found')
                return self.success(data={'plugin': plugin})
            elif quart.request.method == 'DELETE':
                delete_data = quart.request.args.get('delete_data', 'false').lower() == 'true'
                ctx = taskmgr.TaskContext.new()
                wrapper = self.ap.task_mgr.create_user_task(
                    self.ap.plugin_connector.delete_plugin(author, plugin_name, delete_data=delete_data, task_context=ctx),
                    kind='plugin-operation',
                    name=f'plugin-remove-{plugin_name}',
                    label=f'Removing plugin {plugin_name}',
                    context=ctx,
                )

                return self.success(data={'task_id': wrapper.id})

        @self.route(
            '/<author>/<plugin_name>/config',
            methods=['GET', 'PUT'],
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            plugin = await self.ap.plugin_connector.get_plugin_info(author, plugin_name)
            if plugin is None:
                return self.http_status(404, -1, 'plugin not found')

            if quart.request.method == 'GET':
                return self.success(data={'config': plugin['plugin_config']})
            elif quart.request.method == 'PUT':
                data = await quart.request.json

                await self.ap.plugin_connector.set_plugin_config(author, plugin_name, data)

                return self.success(data={})

        @self.route(
            '/<author>/<plugin_name>/icon',
            methods=['GET'],
            auth_type=group.AuthType.NONE,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            icon_data = await self.ap.plugin_connector.get_plugin_icon(author, plugin_name)
            icon_base64 = icon_data['plugin_icon_base64']
            mime_type = icon_data['mime_type']

            icon_data = base64.b64decode(icon_base64)

            return quart.Response(icon_data, mimetype=mime_type)

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            data = await quart.request.json

            ctx = taskmgr.TaskContext.new()
            short_source_str = data['source'][-8:]
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_mgr.install_plugin(data['source'], task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-github',
                label=f'Installing plugin from github ...{short_source_str}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route('/install/marketplace', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            data = await quart.request.json

            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.MARKETPLACE, data, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-marketplace',
                label=f'Installing plugin from marketplace ...{data}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route('/install/local', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            file_bytes = file.read()

            data = {
                'plugin_file': file_bytes,
            }

            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.LOCAL, data, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-local',
                label=f'Installing plugin from local ...{file.filename}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})
