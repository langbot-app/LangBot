from __future__ import annotations

import uuid
import sqlalchemy

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....provider.modelmgr import requester as model_requester
from ....provider import entities as llm_entities


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

    async def test_llm_model(self, model_uuid: str, model_data: dict) -> None:
        runtime_llm_model: model_requester.RuntimeLLMModel | None = None

        if model_uuid != '_':
            for model in self.ap.model_mgr.llm_models:
                if model.model_entity.uuid == model_uuid:
                    runtime_llm_model = model
                    break

            if runtime_llm_model is None:
                raise Exception('model not found')

        else:
            runtime_llm_model = await self.ap.model_mgr.init_runtime_llm_model(model_data)

        await runtime_llm_model.requester.invoke_llm(
            query=None,
            model=runtime_llm_model,
            messages=[llm_entities.Message(role='user', content='Hello, world!')],
            funcs=[],
            extra_args={},
        )


class EmbeddingsModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_embeddings_models(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.EmbeddingsModel))

        models = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingsModel, model) for model in models]

    async def create_embeddings_model(self, model_data: dict) -> str:
        model_data['uuid'] = str(uuid.uuid4())

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_model.EmbeddingsModel).values(**model_data))

        embeddings_model = await self.get_embeddings_model(model_data['uuid'])

        await self.ap.model_mgr.load_embeddings_model(embeddings_model)

        return model_data['uuid']

    async def get_embeddings_model(self, model_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingsModel).where(persistence_model.EmbeddingsModel.uuid == model_uuid)
        )

        model = result.first()

        if model is None:
            return None

        return self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingsModel, model)

    async def update_embeddings_model(self, model_uuid: str, model_data: dict) -> None:
        if 'uuid' in model_data:
            del model_data['uuid']

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.EmbeddingsModel)
            .where(persistence_model.EmbeddingsModel.uuid == model_uuid)
            .values(**model_data)
        )

        await self.ap.model_mgr.remove_embeddings_model(model_uuid)

        embeddings_model = await self.get_embeddings_model(model_uuid)

        await self.ap.model_mgr.load_embeddings_model(embeddings_model)

    async def delete_embeddings_model(self, model_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.EmbeddingsModel).where(persistence_model.EmbeddingsModel.uuid == model_uuid)
        )

        await self.ap.model_mgr.remove_embeddings_model(model_uuid)

    async def test_embeddings_model(self, model_uuid: str, model_data: dict) -> None:
        runtime_embeddings_model: model_requester.RuntimeEmbeddingsModel | None = None

        if model_uuid != '_':
            for model in self.ap.model_mgr.embeddings_models:
                if model.model_entity.uuid == model_uuid:
                    runtime_embeddings_model = model
                    break

            if runtime_embeddings_model is None:
                raise Exception('model not found')

        else:
            runtime_embeddings_model = await self.ap.model_mgr.init_runtime_embeddings_model(model_data)

        await runtime_embeddings_model.requester.invoke_embeddings(
            query=None,
            model=runtime_embeddings_model,
            input_text="Hello, world!",
            extra_args={},
        )
