import quart

from .. import group
from .....utils import constants


@group.group_class('system', '/api/v1/system')
class SystemRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/info', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            return self.success(
                data={
                    'version': constants.semantic_version,
                    'debug': constants.debug_mode,
                    'enable_marketplace': self.ap.instance_config.data.get('plugin', {}).get(
                        'enable_marketplace', True
                    ),
                    'cloud_service_url': (
                        self.ap.instance_config.data.get('plugin', {}).get(
                            'cloud_service_url', 'https://space.langbot.app'
                        )
                        if 'cloud_service_url' in self.ap.instance_config.data.get('plugin', {})
                        else 'https://space.langbot.app'
                    ),
                }
            )

        @self.route('/tasks', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            task_type = quart.request.args.get('type')

            if task_type == '':
                task_type = None

            return self.success(data=self.ap.task_mgr.get_tasks_dict(task_type))

        @self.route('/tasks/<task_id>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _(task_id: str) -> str:
            task = self.ap.task_mgr.get_task_by_id(int(task_id))

            if task is None:
                return self.http_status(404, 404, 'Task not found')

            return self.success(data=task.to_dict())

        @self.route('/debug/exec', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            if not constants.debug_mode:
                return self.http_status(403, 403, 'Forbidden')

            py_code = await quart.request.data

            ap = self.ap

            return self.success(data=exec(py_code, {'ap': ap}))

        @self.route('/debug/tools/call', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            if not constants.debug_mode:
                return self.http_status(403, 403, 'Forbidden')

            data = await quart.request.json

            return self.success(
                data=await self.ap.tool_mgr.execute_func_call(data['tool_name'], data['tool_parameters'])
            )

        @self.route(
            '/debug/plugin/action',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _() -> str:
            if not constants.debug_mode:
                return self.http_status(403, 403, 'Forbidden')

            data = await quart.request.json

            class AnoymousAction:
                value = 'anonymous_action'

                def __init__(self, value: str):
                    self.value = value

            resp = await self.ap.plugin_connector.handler.call_action(
                AnoymousAction(data['action']),
                data['data'],
                timeout=data.get('timeout', 10),
            )

            return self.success(data=resp)

        @self.route(
            '/status/plugin-system',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _() -> str:
            plugin_connector_error = 'ok'
            is_connected = True

            try:
                await self.ap.plugin_connector.ping_plugin_runtime()
            except Exception as e:
                plugin_connector_error = str(e)
                is_connected = False

            return self.success(
                data={
                    'is_enable': self.ap.plugin_connector.is_enable_plugin,
                    'is_connected': is_connected,
                    'plugin_connector_error': plugin_connector_error,
                }
            )
