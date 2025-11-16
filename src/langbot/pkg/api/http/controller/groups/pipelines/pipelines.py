from __future__ import annotations

import quart

from ... import group


@group.group_class('pipelines', '/api/v1/pipelines')
class PipelinesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                sort_by = quart.request.args.get('sort_by', 'created_at')
                sort_order = quart.request.args.get('sort_order', 'DESC')
                return self.success(
                    data={'pipelines': await self.ap.pipeline_service.get_pipelines(sort_by, sort_order)}
                )
            elif quart.request.method == 'POST':
                json_data = await quart.request.json

                pipeline_uuid = await self.ap.pipeline_service.create_pipeline(json_data)

                return self.success(data={'uuid': pipeline_uuid})

        @self.route('/_/metadata', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data={'configs': await self.ap.pipeline_service.get_pipeline_metadata()})

        @self.route(
            '/<pipeline_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(pipeline_uuid: str) -> str:
            if quart.request.method == 'GET':
                pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_uuid)

                if pipeline is None:
                    return self.http_status(404, -1, 'pipeline not found')

                return self.success(data={'pipeline': pipeline})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json

                await self.ap.pipeline_service.update_pipeline(pipeline_uuid, json_data)

                return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.pipeline_service.delete_pipeline(pipeline_uuid)

                return self.success()

        @self.route(
            '/<pipeline_uuid>/extensions', methods=['GET', 'PUT'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(pipeline_uuid: str) -> str:
            if quart.request.method == 'GET':
                # Get current extensions and available plugins
                pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_uuid)
                if pipeline is None:
                    return self.http_status(404, -1, 'pipeline not found')

                plugins = await self.ap.plugin_connector.list_plugins()
                mcp_servers = await self.ap.mcp_service.get_mcp_servers(contain_runtime_info=True)

                return self.success(
                    data={
                        'bound_plugins': pipeline.get('extensions_preferences', {}).get('plugins', []),
                        'available_plugins': plugins,
                        'bound_mcp_servers': pipeline.get('extensions_preferences', {}).get('mcp_servers', []),
                        'available_mcp_servers': mcp_servers,
                    }
                )
            elif quart.request.method == 'PUT':
                # Update bound plugins and MCP servers for this pipeline
                json_data = await quart.request.json
                bound_plugins = json_data.get('bound_plugins', [])
                bound_mcp_servers = json_data.get('bound_mcp_servers', [])

                await self.ap.pipeline_service.update_pipeline_extensions(
                    pipeline_uuid, bound_plugins, bound_mcp_servers
                )

                return self.success()
