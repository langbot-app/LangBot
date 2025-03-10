from __future__ import annotations

import sqlalchemy

from ....core import app
from ....entity.persistence import model


class ModelsService:

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_llm_models(self) -> list[model.LLMModel]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(model.LLMModel)
        )

        result_list = result.all()

        return result_list
    
    async def create_llm_model(self, model: model.LLMModel) -> None:
        pass

    async def get_llm_model(self, model_uuid: str) -> model.LLMModel:
        pass

    async def update_llm_model(self, model: model.LLMModel) -> None:
        pass

    async def delete_llm_model(self, model_uuid: str) -> None:
        pass
