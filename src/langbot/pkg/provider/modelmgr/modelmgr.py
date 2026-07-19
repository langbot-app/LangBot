from __future__ import annotations

import asyncio
import traceback
from typing import TypeVar

import sqlalchemy

from ...api.http.context import (
    ExecutionContext,
    PrincipalContext,
    PrincipalType,
    RequestContext,
)
from ...api.http.service.tenant import TenantContext, require_workspace_uuid
from ...core import app
from ...discover import engine
from ...entity.errors import provider as provider_errors
from ...entity.persistence import model as persistence_model
from ...workspace.entities import WorkspaceExecutionBinding
from ...workspace.errors import WorkspaceError, WorkspaceInvariantError
from . import requester, token


_CacheKey = tuple[str, str, int, str]
_ModelEntity = TypeVar(
    '_ModelEntity',
    persistence_model.LLMModel,
    persistence_model.EmbeddingModel,
    persistence_model.RerankModel,
)


class ModelManager:
    """Workspace-scoped runtime provider and model cache."""

    ap: app.Application

    provider_dict: dict[_CacheKey, requester.RuntimeProvider]
    llm_model_dict: dict[_CacheKey, requester.RuntimeLLMModel]
    embedding_model_dict: dict[_CacheKey, requester.RuntimeEmbeddingModel]
    rerank_model_dict: dict[_CacheKey, requester.RuntimeRerankModel]

    requester_components: list[engine.Component]
    requester_dict: dict[str, type[requester.ProviderAPIRequester]]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.provider_dict = {}
        self.llm_model_dict = {}
        self.embedding_model_dict = {}
        self.rerank_model_dict = {}
        self.requester_components = []
        self.requester_dict = {}

    @staticmethod
    def _get_litellm_provider_from_manifest(component: engine.Component | None) -> str | None:
        if component is None:
            return None

        spec = getattr(component, 'spec', None) or {}
        litellm_provider = None

        if isinstance(spec, dict):
            litellm_provider = spec.get('litellm_provider')
        else:
            getter = getattr(spec, 'get', None)
            if callable(getter):
                try:
                    litellm_provider = getter('litellm_provider')
                except Exception:
                    litellm_provider = None

        if isinstance(litellm_provider, str) and litellm_provider:
            return litellm_provider
        return None

    @staticmethod
    def _context_from_binding(
        binding: WorkspaceExecutionBinding,
        *,
        trigger_principal: PrincipalContext | None = None,
    ) -> ExecutionContext:
        return ExecutionContext(
            instance_uuid=binding.instance_uuid,
            workspace_uuid=binding.workspace_uuid,
            placement_generation=binding.placement_generation,
            trigger_principal=trigger_principal,
        )

    @staticmethod
    def _cache_key(context: ExecutionContext, resource_uuid: str) -> _CacheKey:
        return (
            context.instance_uuid,
            context.workspace_uuid,
            context.placement_generation,
            resource_uuid,
        )

    @staticmethod
    def _ensure_same_scope(
        expected: ExecutionContext,
        actual: ExecutionContext,
        *,
        resource: str,
    ) -> None:
        if (
            actual.instance_uuid != expected.instance_uuid
            or actual.workspace_uuid != expected.workspace_uuid
            or actual.placement_generation != expected.placement_generation
        ):
            raise WorkspaceInvariantError(f'{resource} runtime belongs to another Workspace execution scope')

    @staticmethod
    def _ensure_entity_workspace(entity: object, context: ExecutionContext, *, resource: str) -> None:
        workspace_uuid = getattr(entity, 'workspace_uuid', None)
        if workspace_uuid != context.workspace_uuid:
            raise WorkspaceInvariantError(f'{resource} belongs to another Workspace')

    async def resolve_execution_context(self, context: TenantContext) -> ExecutionContext:
        """Resolve and fence-check an explicit tenant context for runtime access."""

        workspace_uuid = require_workspace_uuid(context)
        expected_generation = None
        supplied_instance_uuid = None
        trigger_principal = None

        if isinstance(context, (RequestContext, ExecutionContext)):
            expected_generation = context.placement_generation
            supplied_instance_uuid = context.instance_uuid
            trigger_principal = context.principal if isinstance(context, RequestContext) else context.trigger_principal

        binding = await self.ap.workspace_service.get_execution_binding(
            workspace_uuid,
            expected_generation=expected_generation,
        )
        if supplied_instance_uuid is not None and supplied_instance_uuid != binding.instance_uuid:
            raise WorkspaceInvariantError('Runtime context belongs to another LangBot instance')

        return self._context_from_binding(binding, trigger_principal=trigger_principal)

    async def initialize(self) -> None:
        self.requester_components = self.ap.discover.get_components_by_kind('LLMAPIRequester')

        requester_dict: dict[str, type[requester.ProviderAPIRequester]] = {}
        for component in self.requester_components:
            litellm_provider = self._get_litellm_provider_from_manifest(component)
            if litellm_provider:
                self.ap.logger.debug(
                    f'Skipping Python class loading for {component.metadata.name} '
                    f'(uses litellm_provider={litellm_provider})'
                )
                continue
            requester_dict[component.metadata.name] = component.get_python_component_class()

        self.requester_dict = requester_dict
        await self.load_models_from_db()

        space_config = self.ap.instance_config.data.get('space', {})
        if space_config.get('disable_models_service', False):
            self.ap.logger.info('LangBot Space Models service is disabled, skipping sync.')
            return

        # Space model synchronization is a legacy OSS-singleton facility. A
        # cloud instance must receive tenant model projections from its control
        # plane and must never infer one Workspace for this global operation.
        try:
            binding = await self.ap.workspace_service.get_local_execution_binding()
        except WorkspaceError as exc:
            self.ap.logger.info(f'Skipping LangBot Space model sync outside an OSS local Workspace: {exc}')
            return

        sync_context = self._context_from_binding(
            binding,
            trigger_principal=PrincipalContext(principal_type=PrincipalType.SYSTEM),
        )
        sync_timeout = space_config.get('models_sync_timeout')
        try:
            if sync_timeout:
                await asyncio.wait_for(
                    self.sync_new_models_from_space(sync_context),
                    timeout=float(sync_timeout),
                )
            else:
                await self.sync_new_models_from_space(sync_context)
        except asyncio.TimeoutError:
            self.ap.logger.warning(f'LangBot Space model sync timed out after {sync_timeout}s, skipping startup sync.')
        except Exception as exc:
            self.ap.logger.warning('Failed to sync new models from LangBot Space, model list may not be updated.')
            self.ap.logger.warning(f'  - Error: {exc}')

    async def load_models_from_db(self) -> None:
        """Load every active projected Workspace into isolated runtime caches."""

        self.ap.logger.info('Loading models from db...')
        self.provider_dict = {}
        self.llm_model_dict = {}
        self.embedding_model_dict = {}
        self.rerank_model_dict = {}
        contexts: dict[str, ExecutionContext] = {}

        async def context_for(workspace_uuid: str | None) -> ExecutionContext:
            if not workspace_uuid:
                raise WorkspaceInvariantError('Runtime model resource has no Workspace')
            cached = contexts.get(workspace_uuid)
            if cached is not None:
                return cached
            binding = await self.ap.workspace_service.get_execution_binding(workspace_uuid)
            resolved = self._context_from_binding(
                binding,
                trigger_principal=PrincipalContext(principal_type=PrincipalType.SYSTEM),
            )
            contexts[workspace_uuid] = resolved
            return resolved

        providers_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider)
        )
        for provider_entity in providers_result.all():
            try:
                context = await context_for(provider_entity.workspace_uuid)
                runtime_provider = await self._build_provider(context, provider_entity)
                self.provider_dict[self._cache_key(context, provider_entity.uuid)] = runtime_provider
            except provider_errors.RequesterNotFoundError as exc:
                self.ap.logger.warning(
                    f'Requester {exc.requester_name} not found, skipping provider {provider_entity.uuid}'
                )
            except Exception as exc:
                self.ap.logger.error(f'Failed to load provider {provider_entity.uuid}: {exc}\n{traceback.format_exc()}')

        await self._load_model_kind(
            persistence_model.LLMModel,
            self.llm_model_dict,
            self._build_llm_model,
            context_for,
        )
        await self._load_model_kind(
            persistence_model.EmbeddingModel,
            self.embedding_model_dict,
            self._build_embedding_model,
            context_for,
        )
        await self._load_model_kind(
            persistence_model.RerankModel,
            self.rerank_model_dict,
            self._build_rerank_model,
            context_for,
        )

    async def _load_model_kind(self, entity_type, cache: dict, builder, context_for) -> None:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(entity_type))
        for model_entity in result.all():
            try:
                context = await context_for(model_entity.workspace_uuid)
                provider = self.provider_dict.get(self._cache_key(context, model_entity.provider_uuid))
                if provider is None:
                    self.ap.logger.warning(
                        f'Provider {model_entity.provider_uuid} not found for model {model_entity.uuid}'
                    )
                    continue
                runtime_model = builder(context, model_entity, provider)
                cache[self._cache_key(context, model_entity.uuid)] = runtime_model
            except Exception as exc:
                self.ap.logger.error(f'Failed to load model {model_entity.uuid}: {exc}\n{traceback.format_exc()}')

    async def sync_new_models_from_space(self, context: ExecutionContext) -> None:
        """Sync legacy Space models for the explicitly selected OSS Workspace."""

        context = await self.resolve_execution_context(context)
        await self.ap.workspace_service.get_local_execution_binding(
            context.workspace_uuid,
            expected_generation=context.placement_generation,
        )
        space_model_provider_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.workspace_uuid == context.workspace_uuid,
                persistence_model.ModelProvider.requester == 'space-chat-completions',
            )
        )
        space_model_provider = space_model_provider_result.first()
        if space_model_provider is None:
            raise provider_errors.ProviderNotFoundError('LangBot Models')

        space_models = await self.ap.space_service.get_models()
        existing_llm_models = {
            model['uuid']: model
            for model in await self.ap.llm_model_service.get_llm_models(context, include_secret=True)
        }
        existing_embedding_models = {
            model['uuid']: model
            for model in await self.ap.embedding_models_service.get_embedding_models(context, include_secret=True)
        }

        created = 0
        updated = 0
        for space_model in space_models:
            if space_model.category == 'chat':
                existing = existing_llm_models.get(space_model.uuid)
                if existing is None:
                    await self.ap.llm_model_service.create_llm_model(
                        context,
                        {
                            'uuid': space_model.uuid,
                            'name': space_model.model_id,
                            'provider_uuid': space_model_provider.uuid,
                            'abilities': space_model.llm_abilities or [],
                            'extra_args': {},
                            'prefered_ranking': space_model.featured_order,
                        },
                        preserve_uuid=True,
                        auto_set_to_default_pipeline=False,
                    )
                    created += 1
                elif existing.get('provider_uuid') == space_model_provider.uuid:
                    desired = {
                        'name': space_model.model_id,
                        'provider_uuid': space_model_provider.uuid,
                        'abilities': space_model.llm_abilities or [],
                        'prefered_ranking': space_model.featured_order,
                    }
                    if (
                        existing.get('name') != desired['name']
                        or list(existing.get('abilities') or []) != list(desired['abilities'])
                        or existing.get('prefered_ranking') != desired['prefered_ranking']
                    ):
                        await self.ap.llm_model_service.update_llm_model(context, space_model.uuid, dict(desired))
                        updated += 1

            elif space_model.category == 'embedding':
                existing = existing_embedding_models.get(space_model.uuid)
                if existing is None:
                    await self.ap.embedding_models_service.create_embedding_model(
                        context,
                        {
                            'uuid': space_model.uuid,
                            'name': space_model.model_id,
                            'provider_uuid': space_model_provider.uuid,
                            'extra_args': {},
                            'prefered_ranking': space_model.featured_order,
                        },
                        preserve_uuid=True,
                    )
                    created += 1
                elif existing.get('provider_uuid') == space_model_provider.uuid:
                    desired = {
                        'name': space_model.model_id,
                        'provider_uuid': space_model_provider.uuid,
                        'prefered_ranking': space_model.featured_order,
                    }
                    if (
                        existing.get('name') != desired['name']
                        or existing.get('prefered_ranking') != desired['prefered_ranking']
                    ):
                        await self.ap.embedding_models_service.update_embedding_model(
                            context,
                            space_model.uuid,
                            dict(desired),
                        )
                        updated += 1

        if created or updated:
            self.ap.logger.info(f'Synced models from LangBot Space: {created} added, {updated} updated.')

    async def init_temporary_runtime_llm_model(
        self,
        context: TenantContext,
        model_info: dict,
    ) -> requester.RuntimeLLMModel:
        execution_context = await self.resolve_execution_context(context)
        provider_info = {**model_info.get('provider', {}), 'workspace_uuid': execution_context.workspace_uuid}
        runtime_provider = await self._build_provider(
            execution_context,
            persistence_model.ModelProvider(**provider_info),
        )
        model_entity = persistence_model.LLMModel(
            workspace_uuid=execution_context.workspace_uuid,
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid=runtime_provider.provider_entity.uuid,
            abilities=model_info.get('abilities', []),
            context_length=model_info.get('context_length'),
            extra_args=model_info.get('extra_args', {}),
        )
        return self._build_llm_model(execution_context, model_entity, runtime_provider)

    async def init_temporary_runtime_embedding_model(
        self,
        context: TenantContext,
        model_info: dict,
    ) -> requester.RuntimeEmbeddingModel:
        execution_context = await self.resolve_execution_context(context)
        provider_info = {**model_info.get('provider', {}), 'workspace_uuid': execution_context.workspace_uuid}
        runtime_provider = await self._build_provider(
            execution_context,
            persistence_model.ModelProvider(**provider_info),
        )
        model_entity = persistence_model.EmbeddingModel(
            workspace_uuid=execution_context.workspace_uuid,
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid=runtime_provider.provider_entity.uuid,
            extra_args=model_info.get('extra_args', {}),
        )
        return self._build_embedding_model(execution_context, model_entity, runtime_provider)

    async def init_temporary_runtime_rerank_model(
        self,
        context: TenantContext,
        model_info: dict,
    ) -> requester.RuntimeRerankModel:
        execution_context = await self.resolve_execution_context(context)
        provider_info = {**model_info.get('provider', {}), 'workspace_uuid': execution_context.workspace_uuid}
        runtime_provider = await self._build_provider(
            execution_context,
            persistence_model.ModelProvider(**provider_info),
        )
        model_entity = persistence_model.RerankModel(
            workspace_uuid=execution_context.workspace_uuid,
            uuid=model_info.get('uuid', ''),
            name=model_info.get('name', ''),
            provider_uuid=runtime_provider.provider_entity.uuid,
            extra_args=model_info.get('extra_args', {}),
        )
        return self._build_rerank_model(execution_context, model_entity, runtime_provider)

    @staticmethod
    def _coerce_provider(
        provider_info: persistence_model.ModelProvider | sqlalchemy.Row | dict,
        context: ExecutionContext,
    ) -> persistence_model.ModelProvider:
        if isinstance(provider_info, sqlalchemy.Row):
            provider_entity = persistence_model.ModelProvider(**provider_info._mapping)
        elif isinstance(provider_info, dict):
            provider_entity = persistence_model.ModelProvider(
                **{**provider_info, 'workspace_uuid': context.workspace_uuid}
            )
        else:
            provider_entity = provider_info
        ModelManager._ensure_entity_workspace(provider_entity, context, resource='Provider')
        return provider_entity

    async def _build_provider(
        self,
        context: ExecutionContext,
        provider_info: persistence_model.ModelProvider | sqlalchemy.Row | dict,
    ) -> requester.RuntimeProvider:
        provider_entity = self._coerce_provider(provider_info, context)
        requester_manifest = self.get_available_requester_manifest_by_name(provider_entity.requester)
        litellm_provider = self._get_litellm_provider_from_manifest(requester_manifest)
        config = {'base_url': provider_entity.base_url}

        if litellm_provider:
            from .requesters import litellmchat

            config['custom_llm_provider'] = litellm_provider
            requester_inst = litellmchat.LiteLLMRequester(ap=self.ap, config=config)
            self.ap.logger.debug(
                f'Using LiteLLMRequester for {provider_entity.requester} '
                f'with custom_llm_provider={config["custom_llm_provider"]}'
            )
        else:
            if provider_entity.requester not in self.requester_dict:
                raise provider_errors.RequesterNotFoundError(provider_entity.requester)
            requester_inst = self.requester_dict[provider_entity.requester](ap=self.ap, config=config)

        await requester_inst.initialize()
        token_mgr = token.TokenManager(name=provider_entity.uuid, tokens=provider_entity.api_keys or [])
        return requester.RuntimeProvider(
            execution_context=context,
            provider_entity=provider_entity,
            token_mgr=token_mgr,
            requester=requester_inst,
        )

    async def load_provider(
        self,
        context: TenantContext,
        provider_info: persistence_model.ModelProvider | sqlalchemy.Row | dict,
    ) -> requester.RuntimeProvider:
        execution_context = await self.resolve_execution_context(context)
        return await self._build_provider(execution_context, provider_info)

    async def cache_provider(self, context: TenantContext, provider: requester.RuntimeProvider) -> None:
        execution_context = await self.resolve_execution_context(context)
        self._ensure_same_scope(execution_context, provider.execution_context, resource='Provider')
        self._ensure_entity_workspace(provider.provider_entity, execution_context, resource='Provider')
        self.provider_dict[self._cache_key(execution_context, provider.provider_entity.uuid)] = provider

    async def get_provider_by_uuid(
        self,
        context: TenantContext,
        provider_uuid: str,
    ) -> requester.RuntimeProvider:
        execution_context = await self.resolve_execution_context(context)
        provider = self.provider_dict.get(self._cache_key(execution_context, provider_uuid))
        if provider is None:
            raise ValueError(f'Model provider {provider_uuid} not found')
        self._ensure_same_scope(execution_context, provider.execution_context, resource='Provider')
        return provider

    async def remove_provider(self, context: TenantContext, provider_uuid: str) -> None:
        execution_context = await self.resolve_execution_context(context)
        self.provider_dict.pop(self._cache_key(execution_context, provider_uuid), None)

    async def reload_provider(self, context: TenantContext, provider_uuid: str) -> None:
        execution_context = await self.resolve_execution_context(context)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.workspace_uuid == execution_context.workspace_uuid,
                persistence_model.ModelProvider.uuid == provider_uuid,
            )
        )
        provider_entity = result.first()
        if provider_entity is None:
            raise provider_errors.ProviderNotFoundError(provider_uuid)

        new_provider = await self._build_provider(execution_context, provider_entity)
        cache_prefix = self._cache_key(execution_context, '')[:3]
        for cache in (self.llm_model_dict, self.embedding_model_dict, self.rerank_model_dict):
            for key, model in cache.items():
                if key[:3] == cache_prefix and model.provider.provider_entity.uuid == provider_uuid:
                    model.provider = new_provider
        self.provider_dict[self._cache_key(execution_context, provider_uuid)] = new_provider

    @staticmethod
    def _coerce_model(model_info: _ModelEntity | sqlalchemy.Row, entity_type: type[_ModelEntity]) -> _ModelEntity:
        if isinstance(model_info, sqlalchemy.Row):
            return entity_type(**model_info._mapping)
        return model_info

    def _validate_model_provider(
        self,
        context: ExecutionContext,
        model_entity: _ModelEntity,
        provider: requester.RuntimeProvider,
    ) -> None:
        self._ensure_entity_workspace(model_entity, context, resource='Model')
        self._ensure_same_scope(context, provider.execution_context, resource='Provider')
        if model_entity.provider_uuid != provider.provider_entity.uuid:
            raise WorkspaceInvariantError('Model references a different provider')

    def _build_llm_model(
        self,
        context: ExecutionContext,
        model_info: persistence_model.LLMModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeLLMModel:
        model_entity = self._coerce_model(model_info, persistence_model.LLMModel)
        self._validate_model_provider(context, model_entity, provider)
        return requester.RuntimeLLMModel(
            execution_context=context,
            model_entity=model_entity,
            provider=provider,
        )

    def _build_embedding_model(
        self,
        context: ExecutionContext,
        model_info: persistence_model.EmbeddingModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeEmbeddingModel:
        model_entity = self._coerce_model(model_info, persistence_model.EmbeddingModel)
        self._validate_model_provider(context, model_entity, provider)
        return requester.RuntimeEmbeddingModel(
            execution_context=context,
            model_entity=model_entity,
            provider=provider,
        )

    def _build_rerank_model(
        self,
        context: ExecutionContext,
        model_info: persistence_model.RerankModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeRerankModel:
        model_entity = self._coerce_model(model_info, persistence_model.RerankModel)
        self._validate_model_provider(context, model_entity, provider)
        return requester.RuntimeRerankModel(
            execution_context=context,
            model_entity=model_entity,
            provider=provider,
        )

    async def load_llm_model_with_provider(
        self,
        context: TenantContext,
        model_info: persistence_model.LLMModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeLLMModel:
        execution_context = await self.resolve_execution_context(context)
        return self._build_llm_model(execution_context, model_info, provider)

    async def load_embedding_model_with_provider(
        self,
        context: TenantContext,
        model_info: persistence_model.EmbeddingModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeEmbeddingModel:
        execution_context = await self.resolve_execution_context(context)
        return self._build_embedding_model(execution_context, model_info, provider)

    async def load_rerank_model_with_provider(
        self,
        context: TenantContext,
        model_info: persistence_model.RerankModel | sqlalchemy.Row,
        provider: requester.RuntimeProvider,
    ) -> requester.RuntimeRerankModel:
        execution_context = await self.resolve_execution_context(context)
        return self._build_rerank_model(execution_context, model_info, provider)

    async def cache_llm_model(self, context: TenantContext, model: requester.RuntimeLLMModel) -> None:
        execution_context = await self.resolve_execution_context(context)
        self._ensure_same_scope(execution_context, model.execution_context, resource='LLM model')
        self.llm_model_dict[self._cache_key(execution_context, model.model_entity.uuid)] = model

    async def cache_embedding_model(
        self,
        context: TenantContext,
        model: requester.RuntimeEmbeddingModel,
    ) -> None:
        execution_context = await self.resolve_execution_context(context)
        self._ensure_same_scope(execution_context, model.execution_context, resource='Embedding model')
        self.embedding_model_dict[self._cache_key(execution_context, model.model_entity.uuid)] = model

    async def cache_rerank_model(self, context: TenantContext, model: requester.RuntimeRerankModel) -> None:
        execution_context = await self.resolve_execution_context(context)
        self._ensure_same_scope(execution_context, model.execution_context, resource='Rerank model')
        self.rerank_model_dict[self._cache_key(execution_context, model.model_entity.uuid)] = model

    async def get_model_by_uuid(self, context: TenantContext, model_uuid: str) -> requester.RuntimeLLMModel:
        execution_context = await self.resolve_execution_context(context)
        model = self.llm_model_dict.get(self._cache_key(execution_context, model_uuid))
        if model is None:
            raise ValueError(f'LLM model {model_uuid} not found')
        self._ensure_same_scope(execution_context, model.execution_context, resource='LLM model')
        return model

    async def get_embedding_model_by_uuid(
        self,
        context: TenantContext,
        model_uuid: str,
    ) -> requester.RuntimeEmbeddingModel:
        execution_context = await self.resolve_execution_context(context)
        model = self.embedding_model_dict.get(self._cache_key(execution_context, model_uuid))
        if model is None:
            raise ValueError(f'Embedding model {model_uuid} not found')
        self._ensure_same_scope(execution_context, model.execution_context, resource='Embedding model')
        return model

    async def get_rerank_model_by_uuid(
        self,
        context: TenantContext,
        model_uuid: str,
    ) -> requester.RuntimeRerankModel:
        execution_context = await self.resolve_execution_context(context)
        model = self.rerank_model_dict.get(self._cache_key(execution_context, model_uuid))
        if model is None:
            raise ValueError(f'Rerank model {model_uuid} not found')
        self._ensure_same_scope(execution_context, model.execution_context, resource='Rerank model')
        return model

    async def remove_llm_model(self, context: TenantContext, model_uuid: str) -> None:
        execution_context = await self.resolve_execution_context(context)
        self.llm_model_dict.pop(self._cache_key(execution_context, model_uuid), None)

    async def remove_embedding_model(self, context: TenantContext, model_uuid: str) -> None:
        execution_context = await self.resolve_execution_context(context)
        self.embedding_model_dict.pop(self._cache_key(execution_context, model_uuid), None)

    async def remove_rerank_model(self, context: TenantContext, model_uuid: str) -> None:
        execution_context = await self.resolve_execution_context(context)
        self.rerank_model_dict.pop(self._cache_key(execution_context, model_uuid), None)

    def get_available_requesters_info(self, model_type: str) -> list[dict]:
        if model_type:
            return [
                component.to_plain_dict()
                for component in self.requester_components
                if model_type in component.spec['support_type']
            ]
        return [component.to_plain_dict() for component in self.requester_components]

    def get_available_requester_info_by_name(self, name: str) -> dict | None:
        for component in self.requester_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None

    def get_available_requester_manifest_by_name(self, name: str) -> engine.Component | None:
        for component in self.requester_components:
            if component.metadata.name == name:
                return component
        return None
