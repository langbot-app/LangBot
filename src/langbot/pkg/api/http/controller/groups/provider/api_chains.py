"""API Chain HTTP Controller"""
import quart

from ... import group


@group.group_class('api_chains', '/api/v1/provider/api-chains')
class APIChainRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                chains = await self.ap.api_chain_service.get_api_chains()
                return self.success(data={'chains': chains})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                chain_uuid = await self.ap.api_chain_service.create_api_chain(json_data)
                return self.success(data={'uuid': chain_uuid})

        @self.route('/<chain_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(chain_uuid: str) -> str:
            if quart.request.method == 'GET':
                chain = await self.ap.api_chain_service.get_api_chain(chain_uuid)
                
                if chain is None:
                    return self.http_status(404, -1, 'API chain not found')
                
                return self.success(data={'chain': chain})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.api_chain_service.update_api_chain(chain_uuid, json_data)
                return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.api_chain_service.delete_api_chain(chain_uuid)
                return self.success()

        @self.route('/<chain_uuid>/test', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(chain_uuid: str) -> str:
            result = await self.ap.api_chain_service.test_api_chain(chain_uuid)
            return self.success(data=result)
