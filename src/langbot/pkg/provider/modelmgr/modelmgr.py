from __future__ import annotations

import sqlalchemy
import traceback

from . import requester
from ...core import app
from ...discover import engine
from . import token
from ...entity.persistence import model as persistence_model
from ...entity.errors import provider as provider_errors
from async_lru import alru_cache


class ModelManager:
    """Model manager"""

    ap: app.Application

    provider_dict: dict[str, requester.RuntimeProvider]
    """运行时模型提供商字典, uuid -> RuntimeProvider"""

    llm_models: list[requester.RuntimeLLMModel]

    embedding_models: list[requester.RuntimeEmbeddingModel]

    requester_components: list[engine.Component]

    requester_dict: dict[str, type[requester.ProviderAPIRequester]]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.llm_models = []
        self.embedding_models = []
        self.requester_components = []
        self.requester_dict = {}

    async def initialize(self):
        self.requester_components = self.ap.discover.get_components_by_kind('LLMAPIRequester')

        requester_dict: dict[str, type[requester.ProviderAPIRequester]] = {}
        for component in self.requester_components:
            requester_dict[component.metadata.name] = component.get_python_component_class()

        self.requester_dict = requester_dict

        await self.load_models_from_db()

        # Check if space models service is disabled
        space_config = self.ap.instance_config.data.get('space', {})
        if space_config.get('disable_models_service', False):
            self.ap.logger.info('LangBot Space Models service is disabled, skipping sync.')
            return

        try:
            await self.sync_new_models_from_space()
        except Exception as e:
            self.ap.logger.warning('Failed to sync new models from LangBot Space, model list may not be updated.')
            self.ap.logger.warning(f'  - Error: {e}')

    async def load_models_from_db(self):
        """Load models from database"""
        self.ap.logger.info('Loading models from db...')

        self.llm_models = []
        self.embedding_models = []

        # Load all providers first
        self.provider_dict = {}
        providers_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider)
        )
        for provider in providers_result.all():
            try:
                runtime_provider = await self.load_provider(provider)
                self.provider_dict[provider.uuid] = runtime_provider
            except provider_errors.RequesterNotFoundError as e:
                self.ap.logger.warning(f'Requester {e.requester_name} not found, skipping provider {provider.uuid}')
                continue
            except Exception as e:
                self.ap.logger.error(f'Failed to load provider {provider.uuid}: {e}\n{traceback.format_exc()}')

        # Load LLM models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))
        llm_models = result.all()
        for llm_model in llm_models:
            try:
                provider = self.provider_dict.get(llm_model.provider_uuid)
                if provider is None:
                    self.ap.logger.warning(f'Provider {llm_model.provider_uuid} not found for model {llm_model.uuid}')
                    continue
                runtime_llm_model = await self.load_llm_model_with_provider(llm_model, provider)
                self.llm_models.append(runtime_llm_model)
            except Exception as e:
                self.ap.logger.error(f'Failed to load model {llm_model.uuid}: {e}\n{traceback.format_exc()}')

        # Load embedding models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.EmbeddingModel))
        embedding_models = result.all()
        for embedding_model in embedding_models:
            try:
                provider = self.provider_dict.get(embedding_model.provider_uuid)
                if provider is None:
                    self.ap.logger.warning(
                        f'Provider {embedding_model.provider_uuid} not found for model {embedding_model.uuid}'
                    )
                    continue
                runtime_embedding_model = await self.load_embedding_model_with_provider(embedding_model, provider)
                self.embedding_models.append(runtime_embedding_model)
            except Exception as e:
                self.ap.logger.error(f'Failed to load model {embedding_model.uuid}: {e}\n{traceback.format_exc()}')

    async def sync_new_models_from_space(self):
        """Sync models from Space"""
        space_model_provider = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.requester == 'space-chat-completions'
            )
        )
        result = space_model_provider.first()
        if result is None:
            raise provider_errors.ProviderNotFoundError('LangBot Models')

        space_model_provider = result

        # get the latest models from space
        space_models = await self.ap.space_service.get_models()

        exists_llm_models_uuids = [m['uuid'] for m in await self.ap.llm_model_service.get_llm_models()]
        exists_embedding_models_uuids = [
            m['uuid'] for m in await self.ap.embedding_models_service.get_embedding_models()
        ]

        for space_model in space_models:
            if space_model.category == 'chat':
                uuid = space_model.uuid

                if uuid in exists_llm_models_uuids:
                    continue

                # model will be automatically loaded
                await self.ap.llm_model_service.create_llm_model(
                    {
                        'uuid': space_model.uuid,
                        'name': space_model.model_id,
                        'provider_uuid': space_model_provider.uuid,
                        'abilities': space_model.llm_abilities or [],
                        'extra_args': {},
                        'prefered_ranking': space_model.featured_order,
                    },
                    preserve_uuid=True,
                )

            elif space_model.category == 'embedding':
                uuid = space_model.uuid

                if uuid in exists_embedding_models_uuids:
                    continue

                # model will be automatically loaded
                await self.ap.embedding_models_service.create_embedding_model(
                    {
                        'uuid': space_model.uuid,
                        'name': space_model.model_id,
                        'provider_uuid': space_model_provider.uuid,
                        'extra_args': {},
                        'prefered_ranking': space_model.featured_order,
                    },
                    preserve_uuid=True,
                )

    async def init_temporary_runtime_llm_model(
        self,
        model_info: dict,
    ) -> requester.RuntimeLLMModel:
        """Initialize runtime LLM model from dict (for testing)"""
        provider_info = model_info.get('provider', {})

        runtime_provider = await self.load_provider(provider_info)

        runtime_llm_model = requester.RuntimeLLMModel(
            model_entity=persistence_model.LLMModel(
                uuid=model_info.get('uuid', ''),
                name=model_info.get('name', ''),
                provider_uuid='',
                abilities=model_info.get('abilities', []),
                extra_args=model_info.get('extra_args', {}),
            ),
            provider=runtime_provider,
        )

        return runtime_llm_model

    async def init_temporary_runtime_embedding_model(
        self,
        model_info: dict,
    ) -> requester.RuntimeEmbeddingModel:
        """Initialize runtime embedding model from dict (for testing)"""
        provider_info = model_info.get('provider', {})
        runtime_provider = await self.load_provider(provider_info)

        runtime_embedding_model = requester.RuntimeEmbeddingModel(
            model_entity=persistence_model.EmbeddingModel(
                uuid=model_info.get('uuid', ''),
                name=model_info.get('name', ''),
                provider_uuid='',
                extra_args=model_info.get('extra_args', {}),
            ),
            provider=runtime_provider,
        )

        return runtime_embedding_model

    async def load_provider(
        self, provider_info: persistence_model.ModelProvider | sqlalchemy.Row | dict
    ) -> requester.RuntimeProvider:
        """Load provider from dict"""
        if isinstance(provider_info, sqlalchemy.Row):
            provider_entity = persistence_model.ModelProvider(**provider_info._mapping)
        elif isinstance(provider_info, dict):
            provider_entity = persistence_model.ModelProvider(**provider_info)
        else:
            provider_entity = provider_info

        if provider_entity.requester not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(provider_entity.requester)

        requester_inst = self.requester_dict[provider_entity.requester](
            ap=self.ap, config={'base_url': provider_entity.base_url}
        )
        await requester_inst.initialize()

        token_mgr = token.TokenManager(name=provider_entity.uuid, tokens=provider_entity.api_keys or [])

        provider = requester.RuntimeProvider(
            provider_entity=provider_entity,
            token_mgr=token_mgr,
            requester=requester_inst,
        )
        return provider

    async def remove_provider(self, provider_uuid: str):
        """Remove provider

        This method will not consider the models using this provider,
        because the models should be removed by the caller.
        """
        del self.provider_dict[provider_uuid]

    async def reload_provider(self, provider_uuid: str):
        """Reload provider"""
        provider_entity = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )
        provider_entity = provider_entity.first()
        if provider_entity is None:
            raise provider_errors.ProviderNotFoundError(provider_uuid)

        new_runtime_provider = await self.load_provider(provider_entity)

        # update refs in runtime models
        for model in self.llm_models:
            if model.provider.provider_entity.uuid == provider_uuid:
                model.provider = new_runtime_provider
        for model in self.embedding_models:
            if model.provider.provider_entity.uuid == provider_uuid:
                model.provider = new_runtime_provider

        # update ref in provider dict
        self.provider_dict[provider_uuid] = new_runtime_provider

    async def load_llm_model_with_provider(
        self,
        model_info: persistence_model.LLMModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeLLMModel:
        """Load LLM model with provider info"""
        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.LLMModel(**model_info._mapping)

        runtime_llm_model = requester.RuntimeLLMModel(
            model_entity=model_info,
            provider=provider,
        )

        return runtime_llm_model

    async def load_embedding_model_with_provider(
        self,
        model_info: persistence_model.EmbeddingModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeEmbeddingModel:
        """Load embedding model with provider info"""
        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.EmbeddingModel(**model_info._mapping)

        runtime_embedding_model = requester.RuntimeEmbeddingModel(
            model_entity=model_info,
            provider=provider,
        )

        return runtime_embedding_model

    async def load_llm_model(self, model_info: dict):
        """Load LLM model from dict (with provider info)"""
        provider_info = model_info.get('provider', {})
        if not provider_info:
            raise ValueError('Provider info is required')

        model_entity = persistence_model.LLMModel(
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid=model_info.get('provider_uuid', ''),
            abilities=model_info.get('abilities', []),
            extra_args=model_info.get('extra_args', {}),
        )

        provider_entity = persistence_model.ModelProvider(
            uuid=provider_info.get('uuid', ''),
            name=provider_info.get('name', ''),
            requester=provider_info.get('requester', ''),
            base_url=provider_info.get('base_url', ''),
            api_keys=provider_info.get('api_keys', []),
        )

        await self.load_llm_model_with_provider(model_entity, provider_entity)

    async def load_embedding_model(self, model_info: dict):
        """Load embedding model from dict (with provider info)"""
        provider_info = model_info.get('provider', {})
        if not provider_info:
            raise ValueError('Provider info is required')

        model_entity = persistence_model.EmbeddingModel(
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid=model_info.get('provider_uuid', ''),
            extra_args=model_info.get('extra_args', {}),
        )

        provider_entity = persistence_model.ModelProvider(
            uuid=provider_info.get('uuid', ''),
            name=provider_info.get('name', ''),
            requester=provider_info.get('requester', ''),
            base_url=provider_info.get('base_url', ''),
            api_keys=provider_info.get('api_keys', []),
        )

        await self.load_embedding_model_with_provider(model_entity, provider_entity)

    @alru_cache(ttl=60 * 5)
    async def get_model_by_uuid(self, uuid: str) -> requester.RuntimeLLMModel:
        """Get LLM model by uuid"""
        for model in self.llm_models:
            if model.model_entity.uuid == uuid:
                return model
        raise ValueError(f'LLM model {uuid} not found')

    @alru_cache(ttl=60 * 5)
    async def get_embedding_model_by_uuid(self, uuid: str) -> requester.RuntimeEmbeddingModel:
        """Get embedding model by uuid"""
        for model in self.embedding_models:
            if model.model_entity.uuid == uuid:
                return model
        raise ValueError(f'Embedding model {uuid} not found')

    async def remove_llm_model(self, model_uuid: str):
        """Remove LLM model"""
        for model in self.llm_models:
            if model.model_entity.uuid == model_uuid:
                self.llm_models.remove(model)
                return

    async def remove_embedding_model(self, model_uuid: str):
        """Remove embedding model"""
        for model in self.embedding_models:
            if model.model_entity.uuid == model_uuid:
                self.embedding_models.remove(model)
                return

    def get_available_requesters_info(self, model_type: str) -> list[dict]:
        """Get all available requesters"""
        if model_type != '':
            return [
                component.to_plain_dict()
                for component in self.requester_components
                if model_type in component.spec['support_type']
            ]
        else:
            return [component.to_plain_dict() for component in self.requester_components]

    def get_available_requester_info_by_name(self, name: str) -> dict | None:
        """Get requester info by name"""
        for component in self.requester_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None

    def get_available_requester_manifest_by_name(self, name: str) -> engine.Component | None:
        """Get requester manifest by name"""
        for component in self.requester_components:
            if component.metadata.name == name:
                return component
        return None
