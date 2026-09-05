from __future__ import annotations

import quart

from .....agent.runner.errors import (
    AgentRunnerError,
    RunnerExecutionError,
    RunnerNotAuthorizedError,
    RunnerNotFoundError,
    RunnerProtocolError,
)
from ...authz import Permission, require_permission
from ...context import RequestContext
from .. import group
from .agent_debug_stream import debug_stream_response


@group.group_class('agents', '/api/v1/agents')
class AgentsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/<agent_uuid>/debug/stream',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def stream_debug(agent_uuid: str, request_context: RequestContext):
            payload = await quart.request.get_json()
            if not isinstance(payload, dict):
                return self.http_status(400, -1, 'Debug payload must be an object')
            return debug_stream_response(self.ap.agent_service, request_context, agent_uuid, payload)

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
            except RunnerExecutionError as exc:
                return self.http_status(
                    422,
                    exc.error_code or 'runner_execution_failed',
                    exc.message,
                )
            except RunnerNotFoundError:
                return self.http_status(
                    409,
                    'runner_not_found',
                    'The configured Agent runner is unavailable',
                )
            except RunnerNotAuthorizedError:
                return self.http_status(
                    403,
                    'runner_not_authorized',
                    'The configured Agent runner is not authorized',
                )
            except RunnerProtocolError:
                return self.http_status(
                    502,
                    'runner_protocol_error',
                    'The Agent runner returned an invalid response',
                )
            except AgentRunnerError:
                return self.http_status(
                    502,
                    'runner_error',
                    'The Agent runner could not complete this test',
                )
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
