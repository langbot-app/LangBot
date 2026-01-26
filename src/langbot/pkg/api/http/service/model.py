from __future__ import annotations

import uuid

import sqlalchemy
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....provider.modelmgr import requester as model_requester


def _parse_provider_api_keys(provider_dict: dict) -> dict:
    """Parse api_keys if it's a JSON string"""
    if isinstance(provider_dict.get('api_keys'), str):
        import json

        try:
            provider_dict['api_keys'] = json.loads(provider_dict['api_keys'])
        except Exception:
            provider_dict['api_keys'] = []
    return provider_dict


class LLMModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_llm_models(self, include_secret: bool = True) -> list[dict]:
        """Get all LLM models with provider info"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))
        models = result.all()

        # Get all providers for lookup
        providers_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider)
        )
        providers = {p.uuid: p for p in providers_result.all()}

        models_list = []
        for model in models:
            model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model)
            provider = providers.get(model.provider_uuid)
            if provider:
                provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
                provider_dict = _parse_provider_api_keys(provider_dict)
                if not include_secret:
                    provider_dict['api_keys'] = ['***'] * len(provider_dict.get('api_keys', []))
                model_dict['provider'] = provider_dict
            models_list.append(model_dict)

        return models_list

    async def get_llm_models_by_provider(self, provider_uuid: str) -> list[dict]:
        """Get LLM models by provider UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(
                persistence_model.LLMModel.provider_uuid == provider_uuid
            )
        )
        models = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, m) for m in models]

    async def create_llm_model(self, model_data: dict, preserve_uuid: bool = False) -> str:
        """Create a new LLM model"""
        if not preserve_uuid:
            model_data['uuid'] = str(uuid.uuid4())

        # Handle provider creation if needed
        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                # Create new provider
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_model.LLMModel).values(**model_data))

        runtime_provider = self.ap.model_mgr.provider_dict.get(model_data['provider_uuid'])
        if runtime_provider is None:
            raise Exception('provider not found')

        runtime_llm_model = await self.ap.model_mgr.load_llm_model_with_provider(
            persistence_model.LLMModel(**model_data),
            runtime_provider,
        )
        self.ap.model_mgr.llm_models.append(runtime_llm_model)

        # set the default pipeline model to this model
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
        """Get a single LLM model with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
        )
        model = result.first()
        if model is None:
            return None

        model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model)

        # Get provider
        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == model.provider_uuid
            )
        )
        provider = provider_result.first()
        if provider:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
            model_dict['provider'] = _parse_provider_api_keys(provider_dict)

        return model_dict

    async def update_llm_model(self, model_uuid: str, model_data: dict) -> None:
        """Update an existing LLM model"""
        if 'uuid' in model_data:
            del model_data['uuid']

        # Handle provider update if needed
        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.LLMModel)
            .where(persistence_model.LLMModel.uuid == model_uuid)
            .values(**model_data)
        )

        await self.ap.model_mgr.remove_llm_model(model_uuid)

        runtime_provider = self.ap.model_mgr.provider_dict.get(model_data['provider_uuid'])
        if runtime_provider is None:
            raise Exception('provider not found')

        runtime_llm_model = await self.ap.model_mgr.load_llm_model_with_provider(
            persistence_model.LLMModel(**model_data),
            runtime_provider,
        )
        self.ap.model_mgr.llm_models.append(runtime_llm_model)

    async def delete_llm_model(self, model_uuid: str) -> None:
        """Delete an LLM model"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid)
        )
        await self.ap.model_mgr.remove_llm_model(model_uuid)

    async def test_llm_model(self, model_uuid: str, model_data: dict) -> None:
        """Test an LLM model"""
        runtime_llm_model: model_requester.RuntimeLLMModel | None = None

        if model_uuid != '_':
            for model in self.ap.model_mgr.llm_models:
                if model.model_entity.uuid == model_uuid:
                    runtime_llm_model = model
                    break
            if runtime_llm_model is None:
                raise Exception('model not found')
        else:
            runtime_llm_model = await self.ap.model_mgr.init_temporary_runtime_llm_model(model_data)

        extra_args = model_data.get('extra_args', {})
        await runtime_llm_model.provider.invoke_llm(
            query=None,
            model=runtime_llm_model,
            messages=[provider_message.Message(role='user', content='Hello, world! Please just reply a "Hello".')],
            funcs=[],
            extra_args=extra_args,
        )


class EmbeddingModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_embedding_models(self) -> list[dict]:
        """Get all embedding models with provider info"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.EmbeddingModel))
        models = result.all()

        providers_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider)
        )
        providers = {p.uuid: p for p in providers_result.all()}

        models_list = []
        for model in models:
            model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model)
            provider = providers.get(model.provider_uuid)
            if provider:
                provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
                model_dict['provider'] = _parse_provider_api_keys(provider_dict)
            models_list.append(model_dict)

        return models_list

    async def get_embedding_models_by_provider(self, provider_uuid: str) -> list[dict]:
        """Get embedding models by provider UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.provider_uuid == provider_uuid
            )
        )
        models = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, m) for m in models]

    async def create_embedding_model(self, model_data: dict, preserve_uuid: bool = False) -> str:
        """Create a new embedding model"""
        if not preserve_uuid:
            model_data['uuid'] = str(uuid.uuid4())

        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.EmbeddingModel).values(**model_data)
        )

        runtime_provider = self.ap.model_mgr.provider_dict.get(model_data['provider_uuid'])
        if runtime_provider is None:
            raise Exception('provider not found')

        runtime_embedding_model = await self.ap.model_mgr.load_embedding_model_with_provider(
            persistence_model.EmbeddingModel(**model_data),
            runtime_provider,
        )
        self.ap.model_mgr.embedding_models.append(runtime_embedding_model)

        return model_data['uuid']

    async def get_embedding_model(self, model_uuid: str) -> dict | None:
        """Get a single embedding model with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == model_uuid
            )
        )
        model = result.first()
        if model is None:
            return None

        model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model)

        provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == model.provider_uuid
            )
        )
        provider = provider_result.first()
        if provider:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
            model_dict['provider'] = _parse_provider_api_keys(provider_dict)

        return model_dict

    async def update_embedding_model(self, model_uuid: str, model_data: dict) -> None:
        """Update an existing embedding model"""
        if 'uuid' in model_data:
            del model_data['uuid']

        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.EmbeddingModel)
            .where(persistence_model.EmbeddingModel.uuid == model_uuid)
            .values(**model_data)
        )

        await self.ap.model_mgr.remove_embedding_model(model_uuid)

        runtime_provider = self.ap.model_mgr.provider_dict.get(model_data['provider_uuid'])
        if runtime_provider is None:
            raise Exception('provider not found')

        runtime_embedding_model = await self.ap.model_mgr.load_embedding_model_with_provider(
            persistence_model.EmbeddingModel(**model_data),
            runtime_provider,
        )
        self.ap.model_mgr.embedding_models.append(runtime_embedding_model)

    async def delete_embedding_model(self, model_uuid: str) -> None:
        """Delete an embedding model"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.uuid == model_uuid
            )
        )
        await self.ap.model_mgr.remove_embedding_model(model_uuid)

    async def test_embedding_model(self, model_uuid: str, model_data: dict) -> None:
        """Test an embedding model"""
        runtime_embedding_model: model_requester.RuntimeEmbeddingModel | None = None

        if model_uuid != '_':
            for model in self.ap.model_mgr.embedding_models:
                if model.model_entity.uuid == model_uuid:
                    runtime_embedding_model = model
                    break
            if runtime_embedding_model is None:
                raise Exception('model not found')
        else:
            runtime_embedding_model = await self.ap.model_mgr.init_temporary_runtime_embedding_model(model_data)

        await runtime_embedding_model.provider.invoke_embedding(
            model=runtime_embedding_model,
            input_text=['Hello, world!'],
            extra_args={},
        )
