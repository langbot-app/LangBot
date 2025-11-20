import quart

from .. import group


@group.group_class('apikeys', '/api/v1/apikeys')
class ApiKeysRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'])
        async def _() -> str:
            if quart.request.method == 'GET':
                keys = await self.ap.apikey_service.get_api_keys()
                return self.success(data={'keys': keys})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                name = json_data.get('name', '')
                description = json_data.get('description', '')

                if not name:
                    return self.http_status(400, -1, 'Name is required')

                key = await self.ap.apikey_service.create_api_key(name, description)
                return self.success(data={'key': key})

        @self.route('/<int:key_id>', methods=['GET', 'PUT', 'DELETE'])
        async def _(key_id: int) -> str:
            if quart.request.method == 'GET':
                key = await self.ap.apikey_service.get_api_key(key_id)
                if key is None:
                    return self.http_status(404, -1, 'API key not found')
                return self.success(data={'key': key})

            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                name = json_data.get('name')
                description = json_data.get('description')

                await self.ap.apikey_service.update_api_key(key_id, name, description)
                return self.success()

            elif quart.request.method == 'DELETE':
                await self.ap.apikey_service.delete_api_key(key_id)
                return self.success()
