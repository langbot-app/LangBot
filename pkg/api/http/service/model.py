from __future__ import annotations

import uuid

import sqlalchemy
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....provider.modelmgr import requester as model_requester


class LLMModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_llm_models(self, include_secret: bool = True) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))

        models = result.all()

        masked_columns = []
        if not include_secret:
            masked_columns = ['api_keys']

        return [
            self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model, masked_columns)
            for model in models
        ]

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

        # Mon Nov 10 2025: Commented for some providers may not support thinking parameter
        # # 有些模型厂商默认开启了思考功能，测试容易延迟
        # extra_args = model_data.get('extra_args', {})
        # if not extra_args or 'thinking' not in extra_args:
        #     extra_args['thinking'] = {'type': 'disabled'}

        await runtime_llm_model.requester.invoke_llm(
            query=None,
            model=runtime_llm_model,
            messages=[provider_message.Message(role='user', content='Hello, world! Please just reply a "Hello".')],
            funcs=[],
            # extra_args=extra_args,
        )


class EmbeddingModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_embedding_models(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.EmbeddingModel))

        models = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model) for model in models]

    async def create_embedding_model(self, model_data: dict) -> str:
        model_data['uuid'] = str(uuid.uuid4())

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.EmbeddingModel).values(**model_data)
        )

        embedding_model = await self.get_embedding_model(model_data['uuid'])

        await self.ap.model_mgr.load_embedding_model(embedding_model)

        return model_data['uuid']

    async def get_embedding_model(self, model_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == model_uuid
            )
        )

        model = result.first()

        if model is None:
            return None

        return self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model)

    async def update_embedding_model(self, model_uuid: str, model_data: dict) -> None:
        if 'uuid' in model_data:
            del model_data['uuid']

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.EmbeddingModel)
            .where(persistence_model.EmbeddingModel.uuid == model_uuid)
            .values(**model_data)
        )

        await self.ap.model_mgr.remove_embedding_model(model_uuid)

        embedding_model = await self.get_embedding_model(model_uuid)

        await self.ap.model_mgr.load_embedding_model(embedding_model)

    async def delete_embedding_model(self, model_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == model_uuid
            )
        )

        await self.ap.model_mgr.remove_embedding_model(model_uuid)

    async def test_embedding_model(self, model_uuid: str, model_data: dict) -> None:
        runtime_embedding_model: model_requester.RuntimeEmbeddingModel | None = None

        if model_uuid != '_':
            for model in self.ap.model_mgr.embedding_models:
                if model.model_entity.uuid == model_uuid:
                    runtime_embedding_model = model
                    break

            if runtime_embedding_model is None:
                raise Exception('model not found')

        else:
            runtime_embedding_model = await self.ap.model_mgr.init_runtime_embedding_model(model_data)

        await runtime_embedding_model.requester.invoke_embedding(
            model=runtime_embedding_model,
            input_text=['Hello, world!'],
            extra_args={},
        )
