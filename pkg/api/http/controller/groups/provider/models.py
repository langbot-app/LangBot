import quart
import uuid

from ... import group
from ......entity.persistence import model


@group.group_class('models/llm', '/api/v1/provider/models/llm')
class LLMModelsRouterGroup(group.RouterGroup):
    
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'])
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={
                    'models': await self.ap.model_service.get_llm_models()
                })
            elif quart.request.method == 'POST':
                json_data = await quart.request.json

                await self.ap.model_service.create_llm_model(json_data)

                return self.success()

        @self.route('/<model_uuid>', methods=['GET', 'DELETE'])
        async def _(model_uuid: str) -> str:
            if quart.request.method == 'GET':
                model = await self.ap.model_service.get_llm_model(model_uuid)

                if model is None:
                    return self.http_status(404, -1, 'model not found')

                return self.success(data={
                    'model': model
                })
            # elif quart.request.method == 'PUT':
            #     json_data = await quart.request.json

            #     await self.ap.model_service.update_llm_model(model_uuid, json_data)

            #     return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.model_service.delete_llm_model(model_uuid)

                return self.success()
