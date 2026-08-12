from __future__ import annotations

import quart

from ....authz import Permission, has_permission
from ....context import RequestContext
from ....service.secrets import redact_secrets
from ... import group


@group.group_class('pipelines', '/api/v1/pipelines')
class PipelinesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            sort_by = quart.request.args.get('sort_by', 'created_at')
            sort_order = quart.request.args.get('sort_order', 'DESC')
            include_secret = has_permission(request_context, Permission.RESOURCE_MANAGE)
            return self.success(
                data={
                    'pipelines': await self.ap.pipeline_service.get_pipelines(
                        request_context,
                        sort_by,
                        sort_order,
                        include_secret=include_secret,
                    )
                }
            )

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            pipeline_uuid = await self.ap.pipeline_service.create_pipeline(request_context, await quart.request.json)
            return self.success(data={'uuid': pipeline_uuid})

        @self.route(
            '/_/metadata',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data={'configs': await self.ap.pipeline_service.get_pipeline_metadata(request_context)})

        @self.route(
            '/<pipeline_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(pipeline_uuid: str, request_context: RequestContext) -> str:
            pipeline = await self.ap.pipeline_service.get_pipeline(
                request_context,
                pipeline_uuid,
                include_secret=has_permission(request_context, Permission.RESOURCE_MANAGE),
            )
            if pipeline is None:
                return self.http_status(404, -1, 'pipeline not found')
            return self.success(data={'pipeline': pipeline})

        @self.route(
            '/<pipeline_uuid>',
            methods=['PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(pipeline_uuid: str, request_context: RequestContext) -> str:
            if quart.request.method == 'PUT':
                try:
                    await self.ap.pipeline_service.update_pipeline(
                        request_context,
                        pipeline_uuid,
                        await quart.request.json,
                    )
                except ValueError as exc:
                    return self.http_status(400, -1, str(exc))
            else:
                await self.ap.pipeline_service.delete_pipeline(request_context, pipeline_uuid)
            return self.success()

        @self.route(
            '/<pipeline_uuid>/copy',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(pipeline_uuid: str, request_context: RequestContext) -> str:
            try:
                new_uuid = await self.ap.pipeline_service.copy_pipeline(request_context, pipeline_uuid)
                return self.success(data={'uuid': new_uuid})
            except ValueError as e:
                return self.http_status(400, -1, str(e))

        @self.route(
            '/<pipeline_uuid>/extensions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(pipeline_uuid: str, request_context: RequestContext) -> str:
            pipeline = await self.ap.pipeline_service.get_pipeline(request_context, pipeline_uuid)
            if pipeline is None:
                return self.http_status(404, -1, 'pipeline not found')

            pipeline_component_kinds = ['Command', 'EventListener', 'Tool']
            if self.ap.plugin_connector.is_enable_plugin:
                await self.ap.plugin_connector.require_workspace_context(request_context)
            plugins = await self.ap.plugin_connector.list_plugins(component_kinds=pipeline_component_kinds)
            mcp_servers = await self.ap.mcp_service.get_mcp_servers(request_context, contain_runtime_info=True)
            available_skills = await self.ap.skill_service.list_skills(request_context)
            extensions_prefs = pipeline.get('extensions_preferences', {})
            return self.success(
                data={
                    'enable_all_plugins': extensions_prefs.get('enable_all_plugins', True),
                    'enable_all_mcp_servers': extensions_prefs.get('enable_all_mcp_servers', True),
                    'enable_all_skills': extensions_prefs.get('enable_all_skills', True),
                    'bound_plugins': extensions_prefs.get('plugins', []),
                    'available_plugins': redact_secrets(plugins),
                    'bound_mcp_servers': extensions_prefs.get('mcp_servers', []),
                    'available_mcp_servers': mcp_servers,
                    'bound_mcp_resources': extensions_prefs.get('mcp_resources', []),
                    'mcp_resource_agent_read_enabled': extensions_prefs.get('mcp_resource_agent_read_enabled', True),
                    'bound_skills': extensions_prefs.get('skills', []),
                    'available_skills': available_skills,
                }
            )

        @self.route(
            '/<pipeline_uuid>/extensions',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(pipeline_uuid: str, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            await self.ap.pipeline_service.update_pipeline_extensions(
                request_context,
                pipeline_uuid,
                json_data.get('bound_plugins', []),
                json_data.get('bound_mcp_servers', []),
                json_data.get('enable_all_plugins', True),
                json_data.get('enable_all_mcp_servers', True),
                bound_skills=json_data.get('bound_skills', []),
                enable_all_skills=json_data.get('enable_all_skills', True),
                bound_mcp_resources=json_data.get('bound_mcp_resources'),
                mcp_resource_agent_read_enabled=json_data.get('mcp_resource_agent_read_enabled'),
            )
            return self.success()
