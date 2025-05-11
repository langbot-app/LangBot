from __future__ import annotations

import uuid
import sqlalchemy

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline


class ModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_llm_models(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))

        models = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model) for model in models]

    async def create_llm_model(self, model_data: dict) -> str:
        model_data['uuid'] = str(uuid.uuid4())

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_model.LLMModel).values(**model_data))

        llm_model = await self.get_llm_model(model_data['uuid'])

        await self.ap.model_mgr.load_llm_model(llm_model)

        # check if default pipeline has no model bound
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.is_default == True
            )
        )
        pipeline = result.first()
        if pipeline is not None and pipeline.config['ai']['local-agent']['model'] == '':
            pipeline_config = pipeline.config
            pipeline_config['ai']['local-agent']['model'] = model_data['uuid']
            pipeline_data = {'config': pipeline_config}
            await self.ap.pipeline_service.update_pipeline(pipeline.uuid, pipeline_data)

        return model_data['uuid']

    async def get_llm_model(self, model_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
        )

        model = result.first()

        if model is None:
            return None

        return self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model)

    async def update_llm_model(self, model_uuid: str, model_data: dict) -> None:
        if 'uuid' in model_data:
            del model_data['uuid']

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.LLMModel)
            .where(persistence_model.LLMModel.uuid == model_uuid)
            .values(**model_data)
        )

        await self.ap.model_mgr.remove_llm_model(model_uuid)

        llm_model = await self.get_llm_model(model_uuid)

        await self.ap.model_mgr.load_llm_model(llm_model)

    async def delete_llm_model(self, model_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
        )

        await self.ap.model_mgr.remove_llm_model(model_uuid)
