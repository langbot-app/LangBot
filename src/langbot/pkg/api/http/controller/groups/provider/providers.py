import quart

from ... import group


@group.group_class('models/providers', '/api/v1/provider/providers')
class ModelProvidersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                providers = await self.ap.provider_service.get_providers()
                # Add model counts
                for provider in providers:
                    counts = await self.ap.provider_service.get_provider_model_counts(provider['uuid'])
                    provider['llm_count'] = counts['llm_count']
                    provider['embedding_count'] = counts['embedding_count']
                return self.success(data={'providers': providers})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                provider_uuid = await self.ap.provider_service.create_provider(json_data)
                return self.success(data={'uuid': provider_uuid})

        @self.route(
            '/<provider_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def _(provider_uuid: str) -> str:
            if quart.request.method == 'GET':
                provider = await self.ap.provider_service.get_provider(provider_uuid)
                if provider is None:
                    return self.http_status(404, -1, 'provider not found')
                counts = await self.ap.provider_service.get_provider_model_counts(provider_uuid)
                provider['llm_count'] = counts['llm_count']
                provider['embedding_count'] = counts['embedding_count']
                return self.success(data={'provider': provider})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.provider_service.update_provider(provider_uuid, json_data)
                return self.success()
            elif quart.request.method == 'DELETE':
                try:
                    await self.ap.provider_service.delete_provider(provider_uuid)
                    return self.success()
                except ValueError as e:
                    return self.http_status(400, -1, str(e))
