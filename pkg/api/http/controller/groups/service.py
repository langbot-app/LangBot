import quart

from ... import group


@group.group_class('service/models', '/api/service/v1/models')
class ServiceModelsRouterGroup(group.RouterGroup):
    """External service API for managing LLM models with API key authentication"""

    async def initialize(self) -> None:
        @self.route('/llm', methods=['GET', 'POST'], auth_type=group.AuthType.API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                models = await self.ap.llm_model_service.get_llm_models(include_secret=False)
                return self.success(data={'models': models})

            elif quart.request.method == 'POST':
                json_data = await quart.request.json

                model_uuid = await self.ap.llm_model_service.create_llm_model(json_data)

                return self.success(data={'uuid': model_uuid})

        @self.route('/llm/<model_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.API_KEY)
        async def _(model_uuid: str) -> str:
            if quart.request.method == 'GET':
                model = await self.ap.llm_model_service.get_llm_model(model_uuid)

                if model is None:
                    return self.http_status(404, -1, 'Model not found')

                return self.success(data={'model': model})

            elif quart.request.method == 'PUT':
                json_data = await quart.request.json

                await self.ap.llm_model_service.update_llm_model(model_uuid, json_data)

                return self.success()

            elif quart.request.method == 'DELETE':
                await self.ap.llm_model_service.delete_llm_model(model_uuid)

                return self.success()

        @self.route('/llm/<model_uuid>/test', methods=['POST'], auth_type=group.AuthType.API_KEY)
        async def _(model_uuid: str) -> str:
            json_data = await quart.request.json

            await self.ap.llm_model_service.test_llm_model(model_uuid, json_data)

            return self.success()
