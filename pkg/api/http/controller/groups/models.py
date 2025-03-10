import quart

from .. import group
from .....entity.persistence import model


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
                pass

        @self.route('/<model_uuid>', methods=['GET', 'PUT', 'DELETE'])
        async def _(model_uuid: str) -> str:
            if quart.request.method == 'GET':
                pass
            elif quart.request.method == 'PUT':
                pass
            elif quart.request.method == 'DELETE':
                pass