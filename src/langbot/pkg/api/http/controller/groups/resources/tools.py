from __future__ import annotations

import quart

from ....authz import Permission
from ....context import RequestContext
from ... import group


@group.group_class('tools', '/api/v1/tools')
class ToolsRouterGroup(group.RouterGroup):
    async def _get_scoped_tool_catalog(
        self,
        request_context: RequestContext,
    ) -> list[dict] | None:
        pipeline_uuid = quart.request.args.get('pipeline_uuid') or quart.request.args.get('pipeline_id')
        try:
            return await self.call_application('tool.list', request_context, {'pipeline_uuid': pipeline_uuid})
        except FileNotFoundError:
            return None

    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            """获取所有可用工具列表"""
            catalog = await self._get_scoped_tool_catalog(request_context)
            if catalog is None:
                return self.http_status(404, -1, 'pipeline not found')
            return self.success(data={'tools': catalog})

        @self.route(
            '/<path:tool_name>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(tool_name: str, request_context: RequestContext) -> str:
            """获取特定工具详情"""
            catalog = await self._get_scoped_tool_catalog(request_context)
            if catalog is None:
                return self.http_status(404, -1, 'pipeline not found')

            for tool in catalog:
                if tool.get('name') == tool_name:
                    return self.success(
                        data={
                            'tool': {
                                'name': tool['name'],
                                'description': tool.get('description') or '',
                                'human_desc': tool.get('human_desc') or '',
                                'parameters': tool.get('parameters') or {},
                                'source': tool.get('source'),
                                'source_name': tool.get('source_name'),
                                'source_id': tool.get('source_id'),
                            }
                        }
                    )

            return self.http_status(404, -1, f'Tool not found: {tool_name}')
