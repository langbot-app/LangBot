import quart

from ... import group


@group.group_class('models/llm', '/api/v1/provider/models/llm')
class LLMModelsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'models': await self.ap.llm_model_service.get_llm_models()})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json

                model_uuid = await self.ap.llm_model_service.create_llm_model(json_data)

                return self.success(data={'uuid': model_uuid})

        @self.route('/<model_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(model_uuid: str) -> str:
            if quart.request.method == 'GET':
                model = await self.ap.llm_model_service.get_llm_model(model_uuid)

                if model is None:
                    return self.http_status(404, -1, 'model not found')

                return self.success(data={'model': model})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json

                await self.ap.llm_model_service.update_llm_model(model_uuid, json_data)

                return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.llm_model_service.delete_llm_model(model_uuid)

                return self.success()

        @self.route('/<model_uuid>/test', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(model_uuid: str) -> str:
            json_data = await quart.request.json

            await self.ap.llm_model_service.test_llm_model(model_uuid, json_data)

            return self.success()


@group.group_class('models/embedding', '/api/v1/provider/models/embedding')
class EmbeddingModelsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'models': await self.ap.embedding_models_service.get_embedding_models()})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json

                model_uuid = await self.ap.embedding_models_service.create_embedding_model(json_data)

                return self.success(data={'uuid': model_uuid})

        @self.route('/<model_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(model_uuid: str) -> str:
            if quart.request.method == 'GET':
                model = await self.ap.embedding_models_service.get_embedding_model(model_uuid)

                if model is None:
                    return self.http_status(404, -1, 'model not found')

                return self.success(data={'model': model})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json

                await self.ap.embedding_models_service.update_embedding_model(model_uuid, json_data)

                return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.embedding_models_service.delete_embedding_model(model_uuid)

                return self.success()

        @self.route('/<model_uuid>/test', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(model_uuid: str) -> str:
            json_data = await quart.request.json

            await self.ap.embedding_models_service.test_embedding_model(model_uuid, json_data)

            return self.success()
