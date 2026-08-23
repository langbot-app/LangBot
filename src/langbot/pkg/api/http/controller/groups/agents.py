from __future__ import annotations

import quart

from ...authz import Permission, require_permission
from ...context import RequestContext
from .. import group


@group.group_class('agents', '/api/v1/agents')
class AgentsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET', 'POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            if quart.request.method == 'GET':
                sort_by = quart.request.args.get('sort_by', 'updated_at')
                sort_order = quart.request.args.get('sort_order', 'DESC')
                return self.success(
                    data={
                        'agents': await self.ap.agent_service.get_agents(
                            request_context,
                            sort_by,
                            sort_order,
                        )
                    }
                )

            json_data = await quart.request.json
            require_permission(request_context, Permission.RESOURCE_MANAGE)
            try:
                created = await self.ap.agent_service.create_agent(request_context, json_data)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data=created)

        @self.route(
            '/_/metadata',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.ap.agent_service.get_agent_metadata(request_context))

        @self.route(
            '/<agent_uuid>/debug',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def _(agent_uuid: str, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            try:
                result = await self.ap.agent_service.debug_agent(
                    request_context,
                    agent_uuid,
                    json_data or {},
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data=result)

        @self.route(
            '/<agent_uuid>',
            methods=['GET', 'PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(agent_uuid: str, request_context: RequestContext) -> str:
            if quart.request.method == 'GET':
                agent = await self.ap.agent_service.get_agent(request_context, agent_uuid)
                if agent is None:
                    return self.http_status(404, -1, 'agent not found')
                return self.success(data={'agent': agent})

            if quart.request.method == 'PUT':
                require_permission(request_context, Permission.RESOURCE_MANAGE)
                json_data = await quart.request.json
                try:
                    await self.ap.agent_service.update_agent(request_context, agent_uuid, json_data)
                except ValueError as exc:
                    return self.http_status(400, -1, str(exc))
                return self.success()

            require_permission(request_context, Permission.RESOURCE_MANAGE)
            await self.ap.agent_service.delete_agent(request_context, agent_uuid)
            return self.success()
