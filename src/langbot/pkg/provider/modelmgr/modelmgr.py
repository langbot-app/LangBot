from __future__ import annotations

import sqlalchemy
import traceback

from . import requester
from ...core import app
from ...discover import engine
from . import token
from ...entity.persistence import model as persistence_model
from ...entity.errors import provider as provider_errors


class ModelManager:
    """Model manager"""

    ap: app.Application

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

    async def load_models_from_db(self):
        """Load models from database"""
        self.ap.logger.info('Loading models from db...')

        self.llm_models = []
        self.embedding_models = []

        # Load all providers first
        providers_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider)
        )
        providers = {p.uuid: p for p in providers_result.all()}

        # Load LLM models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.LLMModel))
        llm_models = result.all()
        for llm_model in llm_models:
            try:
                provider = providers.get(llm_model.provider_uuid)
                if provider is None:
                    self.ap.logger.warning(f'Provider {llm_model.provider_uuid} not found for model {llm_model.uuid}')
                    continue
                await self.load_llm_model_with_provider(llm_model, provider)
            except provider_errors.RequesterNotFoundError as e:
                self.ap.logger.warning(f'Requester {e.requester_name} not found, skipping llm model {llm_model.uuid}')
            except Exception as e:
                self.ap.logger.error(f'Failed to load model {llm_model.uuid}: {e}\n{traceback.format_exc()}')

        # Load embedding models
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.EmbeddingModel))
        embedding_models = result.all()
        for embedding_model in embedding_models:
            try:
                provider = providers.get(embedding_model.provider_uuid)
                if provider is None:
                    self.ap.logger.warning(
                        f'Provider {embedding_model.provider_uuid} not found for model {embedding_model.uuid}'
                    )
                    continue
                await self.load_embedding_model_with_provider(embedding_model, provider)
            except provider_errors.RequesterNotFoundError as e:
                self.ap.logger.warning(
                    f'Requester {e.requester_name} not found, skipping embedding model {embedding_model.uuid}'
                )
            except Exception as e:
                self.ap.logger.error(f'Failed to load model {embedding_model.uuid}: {e}\n{traceback.format_exc()}')

    async def init_runtime_llm_model(
        self,
        model_info: dict,
    ):
        """Initialize runtime LLM model from dict (for testing)"""
        provider_info = model_info.get('provider', {})
        requester_name = provider_info.get('requester', '')
        base_url = provider_info.get('base_url', '')
        api_keys = provider_info.get('api_keys', [])

        if requester_name not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(requester_name)

        requester_cfg = {'base_url': base_url}
        requester_inst = self.requester_dict[requester_name](ap=self.ap, config=requester_cfg)
        await requester_inst.initialize()

        # Create a temporary model entity
        model_entity = persistence_model.LLMModel(
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid='',
            abilities=model_info.get('abilities', []),
            extra_args=model_info.get('extra_args', {}),
        )

        runtime_llm_model = requester.RuntimeLLMModel(
            model_entity=model_entity,
            token_mgr=token.TokenManager(name=model_entity.uuid, tokens=api_keys),
            requester=requester_inst,
        )

        return runtime_llm_model

    async def init_runtime_embedding_model(
        self,
        model_info: dict,
    ):
        """Initialize runtime embedding model from dict (for testing)"""
        provider_info = model_info.get('provider', {})
        requester_name = provider_info.get('requester', '')
        base_url = provider_info.get('base_url', '')
        api_keys = provider_info.get('api_keys', [])

        if requester_name not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(requester_name)

        requester_cfg = {'base_url': base_url}
        requester_inst = self.requester_dict[requester_name](ap=self.ap, config=requester_cfg)
        await requester_inst.initialize()

        model_entity = persistence_model.EmbeddingModel(
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid='',
            extra_args=model_info.get('extra_args', {}),
        )

        runtime_embedding_model = requester.RuntimeEmbeddingModel(
            model_entity=model_entity,
            token_mgr=token.TokenManager(name=model_entity.uuid, tokens=api_keys),
            requester=requester_inst,
        )

        return runtime_embedding_model

    async def load_llm_model_with_provider(
        self,
        model_info: persistence_model.LLMModel | sqlalchemy.Row,
        provider: persistence_model.ModelProvider | sqlalchemy.Row,
    ):
        """Load LLM model with provider info"""
        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.LLMModel(**model_info._mapping)
        if isinstance(provider, sqlalchemy.Row):
            provider = persistence_model.ModelProvider(**provider._mapping)

        if provider.requester not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(provider.requester)

        requester_cfg = {'base_url': provider.base_url}
        requester_inst = self.requester_dict[provider.requester](ap=self.ap, config=requester_cfg)
        await requester_inst.initialize()

        runtime_llm_model = requester.RuntimeLLMModel(
            model_entity=model_info,
            token_mgr=token.TokenManager(name=model_info.uuid, tokens=provider.api_keys or []),
            requester=requester_inst,
        )

        self.llm_models.append(runtime_llm_model)

    async def load_embedding_model_with_provider(
        self,
        model_info: persistence_model.EmbeddingModel | sqlalchemy.Row,
        provider: persistence_model.ModelProvider | sqlalchemy.Row,
    ):
        """Load embedding model with provider info"""
        if isinstance(model_info, sqlalchemy.Row):
            model_info = persistence_model.EmbeddingModel(**model_info._mapping)
        if isinstance(provider, sqlalchemy.Row):
            provider = persistence_model.ModelProvider(**provider._mapping)

        if provider.requester not in self.requester_dict:
            raise provider_errors.RequesterNotFoundError(provider.requester)

        requester_cfg = {'base_url': provider.base_url}
        requester_inst = self.requester_dict[provider.requester](ap=self.ap, config=requester_cfg)
        await requester_inst.initialize()

        runtime_embedding_model = requester.RuntimeEmbeddingModel(
            model_entity=model_info,
            token_mgr=token.TokenManager(name=model_info.uuid, tokens=provider.api_keys or []),
            requester=requester_inst,
        )

        self.embedding_models.append(runtime_embedding_model)

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

    async def get_model_by_uuid(self, uuid: str) -> requester.RuntimeLLMModel:
        """Get LLM model by uuid"""
        for model in self.llm_models:
            if model.model_entity.uuid == uuid:
                return model
        raise ValueError(f'LLM model {uuid} not found')

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
