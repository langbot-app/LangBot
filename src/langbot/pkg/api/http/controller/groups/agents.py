from __future__ import annotations

import quart

from .. import group


@group.group_class('agents', '/api/v1/agents')
class AgentsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                sort_by = quart.request.args.get('sort_by', 'updated_at')
                sort_order = quart.request.args.get('sort_order', 'DESC')
                return self.success(data={'agents': await self.ap.agent_service.get_agents(sort_by, sort_order)})

            json_data = await quart.request.json
            created = await self.ap.agent_service.create_agent(json_data)
            return self.success(data=created)

        @self.route('/_/metadata', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            return self.success(data=await self.ap.agent_service.get_agent_metadata())

        @self.route('/<agent_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(agent_uuid: str) -> str:
            if quart.request.method == 'GET':
                agent = await self.ap.agent_service.get_agent(agent_uuid)
                if agent is None:
                    return self.http_status(404, -1, 'agent not found')
                return self.success(data={'agent': agent})

            if quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.agent_service.update_agent(agent_uuid, json_data)
                return self.success()

            await self.ap.agent_service.delete_agent(agent_uuid)
            return self.success()
