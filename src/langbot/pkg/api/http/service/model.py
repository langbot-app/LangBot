from __future__ import annotations

import uuid

import sqlalchemy
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ....core import app
from ....entity.persistence import model as persistence_model
from ....entity.persistence import pipeline as persistence_pipeline
from ....provider.modelmgr import requester as model_requester
from ....workspace.errors import WorkspaceNotFoundError
from .secrets import mask_secret_value, redact_secrets, restore_secret_placeholders
from .tenant import TenantContext, require_workspace_uuid, scope_statement


def _parse_provider_api_keys(provider_dict: dict) -> dict:
    """Parse api_keys if it's a JSON string"""
    if isinstance(provider_dict.get('api_keys'), str):
        import json

        try:
            provider_dict['api_keys'] = json.loads(provider_dict['api_keys'])
        except Exception:
            provider_dict['api_keys'] = []
    return provider_dict


def _runtime_model_data(model_uuid: str, model_data: dict) -> dict:
    """Return model data for rebuilding runtime models after an update.

    Update payloads intentionally omit uuid before writing to the database.
    Runtime model entities still need the stable uuid so pipeline configs can
    resolve the in-memory model immediately after an edit, without requiring a
    process restart.
    """
    return {**model_data, 'uuid': model_uuid}


def _redact_model_secrets(model_data: dict) -> dict:
    """Return a copy with model args and embedded provider credentials masked."""

    redacted = model_data.copy()
    if 'extra_args' in redacted:
        redacted['extra_args'] = redact_secrets(redacted['extra_args'])
    if isinstance(redacted.get('provider'), dict):
        provider = redacted['provider'].copy()
        # ModelProvider never contains another provider. Dropping this key also
        # makes the serializer robust to a reused/self-referential test double.
        provider.pop('provider', None)
        if 'api_keys' in provider:
            provider['api_keys'] = mask_secret_value(provider['api_keys'])
        redacted['provider'] = provider
    return redacted


async def _validate_provider_supports(
    ap: app.Application,
    context: TenantContext,
    provider_uuid: str,
    model_type: str,
) -> None:
    """Validate that the provider's requester declares support for ``model_type``.

    ``model_type`` is one of the manifest ``support_type`` values:
    'llm', 'text-embedding', 'rerank'. Raises ValueError when the requester
    manifest does not list the requested type. This is a server-side guard so
    a model cannot be attached to a provider that does not support it, even if
    the frontend tab restriction is bypassed.
    """
    model_mgr = getattr(ap, 'model_mgr', None)
    if model_mgr is None:
        return

    get_provider = getattr(model_mgr, 'get_provider_by_uuid', None)
    if not callable(get_provider):
        return
    try:
        runtime_provider = await get_provider(context, provider_uuid)
    except ValueError:
        return

    requester_name = getattr(getattr(runtime_provider, 'provider_entity', None), 'requester', None)
    if not requester_name:
        return

    get_manifest = getattr(model_mgr, 'get_available_requester_manifest_by_name', None)
    if not callable(get_manifest):
        return
    manifest = get_manifest(requester_name)
    if manifest is None:
        return

    spec = getattr(manifest, 'spec', None) or {}
    support_type = spec.get('support_type') if isinstance(spec, dict) else None
    # When a manifest omits support_type, do not block (backward compatible).
    if not support_type:
        return
    if model_type not in support_type:
        raise ValueError(f'Provider requester "{requester_name}" does not support {model_type} models')


async def _require_workspace_provider(
    ap: app.Application,
    context: TenantContext,
    provider_uuid: str,
) -> dict:
    """Require the referenced provider to belong to the active Workspace."""

    provider = await ap.provider_service.get_provider(context, provider_uuid)
    if provider is None:
        raise WorkspaceNotFoundError('Provider not found')
    return provider


async def _require_runtime_provider(
    ap: app.Application,
    context: TenantContext,
    provider_uuid: str,
) -> model_requester.RuntimeProvider:
    try:
        return await ap.model_mgr.get_provider_by_uuid(context, provider_uuid)
    except ValueError as exc:
        raise Exception('provider not found') from exc


class LLMModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_llm_models(self, context: TenantContext, include_secret: bool = False) -> list[dict]:
        """Get all LLM models with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(persistence_model.LLMModel), persistence_model.LLMModel, context)
        )
        models = result.all()

        # Get all providers for lookup
        providers_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider), persistence_model.ModelProvider, context
            )
        )
        providers = {p.uuid: p for p in providers_result.all()}

        models_list = []
        for model in models:
            model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model)
            provider = providers.get(model.provider_uuid)
            if provider:
                provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
                provider_dict = _parse_provider_api_keys(provider_dict)
                model_dict['provider'] = provider_dict
            if not include_secret:
                model_dict = _redact_model_secrets(model_dict)
            models_list.append(model_dict)

        return models_list

    async def get_llm_models_by_provider(
        self,
        context: TenantContext,
        provider_uuid: str,
        *,
        include_secret: bool = False,
    ) -> list[dict]:
        """Get LLM models by provider UUID"""
        await _require_workspace_provider(self.ap, context, provider_uuid)
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.LLMModel).where(
                    persistence_model.LLMModel.provider_uuid == provider_uuid
                ),
                persistence_model.LLMModel,
                context,
            )
        )
        models = result.all()
        serialized = [self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, m) for m in models]
        return serialized if include_secret else [_redact_model_secrets(model) for model in serialized]

    async def create_llm_model(
        self,
        context: TenantContext,
        model_data: dict,
        preserve_uuid: bool = False,
        auto_set_to_default_pipeline: bool = True,
    ) -> str:
        """Create a new LLM model"""
        workspace_uuid = require_workspace_uuid(context)
        model_data = model_data.copy()
        if not preserve_uuid:
            model_data['uuid'] = str(uuid.uuid4())
        model_data['workspace_uuid'] = workspace_uuid
        if 'extra_args' in model_data:
            model_data['extra_args'] = restore_secret_placeholders(model_data['extra_args'])

        # Handle provider creation if needed
        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                # Create new provider
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    context,
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await _require_workspace_provider(self.ap, context, model_data['provider_uuid'])
        await _validate_provider_supports(self.ap, context, model_data['provider_uuid'], 'llm')

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_model.LLMModel).values(**model_data))

        runtime_provider = await _require_runtime_provider(self.ap, context, model_data['provider_uuid'])
        runtime_llm_model = await self.ap.model_mgr.load_llm_model_with_provider(
            context,
            persistence_model.LLMModel(**model_data),
            runtime_provider,
        )
        await self.ap.model_mgr.cache_llm_model(context, runtime_llm_model)

        if auto_set_to_default_pipeline:
            # set the default pipeline model to this model
            result = await self.ap.persistence_mgr.execute_async(
                scope_statement(
                    sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                        persistence_pipeline.LegacyPipeline.is_default == True
                    ),
                    persistence_pipeline.LegacyPipeline,
                    workspace_uuid,
                )
            )
            pipeline = result.first()
            if pipeline is not None:
                model_config = pipeline.config.get('ai', {}).get('local-agent', {}).get('model', {})
                if not model_config.get('primary', ''):
                    pipeline_config = pipeline.config
                    pipeline_config['ai']['local-agent']['model'] = {
                        'primary': model_data['uuid'],
                        'fallbacks': [],
                    }
                    pipeline_data = {'config': pipeline_config}
                    await self.ap.pipeline_service.update_pipeline(context, pipeline.uuid, pipeline_data)

        return model_data['uuid']

    async def get_llm_model(
        self,
        context: TenantContext,
        model_uuid: str,
        include_secret: bool = False,
    ) -> dict | None:
        """Get a single LLM model with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid),
                persistence_model.LLMModel,
                context,
            )
        )
        model = result.first()
        if model is None:
            return None

        model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.LLMModel, model)

        # Get provider
        provider_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == model.provider_uuid
                ),
                persistence_model.ModelProvider,
                context,
            )
        )
        provider = provider_result.first()
        if provider:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
            provider_dict = _parse_provider_api_keys(provider_dict)
            model_dict['provider'] = provider_dict

        if not include_secret:
            model_dict = _redact_model_secrets(model_dict)

        return model_dict

    async def update_llm_model(self, context: TenantContext, model_uuid: str, model_data: dict) -> None:
        """Update an existing LLM model"""
        existing_model = await self.get_llm_model(context, model_uuid, include_secret=True)
        if existing_model is None:
            raise WorkspaceNotFoundError('Model not found')
        model_data = model_data.copy()
        model_data.pop('uuid', None)
        model_data.pop('workspace_uuid', None)
        if 'extra_args' in model_data:
            model_data['extra_args'] = restore_secret_placeholders(
                model_data['extra_args'],
                existing_model.get('extra_args', {}),
            )

        # Handle provider update if needed
        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    context,
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        provider_uuid = model_data.get('provider_uuid', existing_model['provider_uuid'])
        await _require_workspace_provider(self.ap, context, provider_uuid)
        await _validate_provider_supports(self.ap, context, provider_uuid, 'llm')

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_model.LLMModel)
                .where(persistence_model.LLMModel.uuid == model_uuid)
                .values(**model_data),
                persistence_model.LLMModel,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Model not found')

        await self.ap.model_mgr.remove_llm_model(context, model_uuid)
        runtime_provider = await _require_runtime_provider(self.ap, context, provider_uuid)
        runtime_llm_model = await self.ap.model_mgr.load_llm_model_with_provider(
            context,
            persistence_model.LLMModel(
                **_runtime_model_data(
                    model_uuid,
                    {
                        key: value
                        for key, value in {**existing_model, **model_data, 'provider_uuid': provider_uuid}.items()
                        if key not in {'provider', 'created_at', 'updated_at'}
                    },
                )
            ),
            runtime_provider,
        )
        await self.ap.model_mgr.cache_llm_model(context, runtime_llm_model)

    async def delete_llm_model(self, context: TenantContext, model_uuid: str) -> None:
        """Delete an LLM model"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_model.LLMModel).where(persistence_model.LLMModel.uuid == model_uuid),
                persistence_model.LLMModel,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Model not found')
        await self.ap.model_mgr.remove_llm_model(context, model_uuid)

    async def test_llm_model(self, context: TenantContext, model_uuid: str, model_data: dict) -> None:
        """Test an LLM model"""
        require_workspace_uuid(context)
        runtime_llm_model: model_requester.RuntimeLLMModel | None = None

        if model_uuid != '_':
            if await self.get_llm_model(context, model_uuid) is None:
                raise WorkspaceNotFoundError('Model not found')
            runtime_llm_model = await self.ap.model_mgr.get_model_by_uuid(context, model_uuid)
        else:
            runtime_llm_model = await self.ap.model_mgr.init_temporary_runtime_llm_model(context, model_data)

        extra_args = model_data.get('extra_args', {})
        await runtime_llm_model.provider.invoke_llm(
            query=None,
            model=runtime_llm_model,
            messages=[provider_message.Message(role='user', content='Hello, world! Please just reply a "Hello".')],
            funcs=[],
            extra_args=extra_args,
            execution_context=runtime_llm_model.execution_context,
        )


class EmbeddingModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_embedding_models(self, context: TenantContext, include_secret: bool = False) -> list[dict]:
        """Get all embedding models with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.EmbeddingModel), persistence_model.EmbeddingModel, context
            )
        )
        models = result.all()

        providers_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider), persistence_model.ModelProvider, context
            )
        )
        providers = {p.uuid: p for p in providers_result.all()}

        models_list = []
        for model in models:
            model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model)
            provider = providers.get(model.provider_uuid)
            if provider:
                provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
                provider_dict = _parse_provider_api_keys(provider_dict)
                model_dict['provider'] = provider_dict
            if not include_secret:
                model_dict = _redact_model_secrets(model_dict)
            models_list.append(model_dict)

        return models_list

    async def get_embedding_models_by_provider(
        self,
        context: TenantContext,
        provider_uuid: str,
        *,
        include_secret: bool = False,
    ) -> list[dict]:
        """Get embedding models by provider UUID"""
        await _require_workspace_provider(self.ap, context, provider_uuid)
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.EmbeddingModel).where(
                    persistence_model.EmbeddingModel.provider_uuid == provider_uuid
                ),
                persistence_model.EmbeddingModel,
                context,
            )
        )
        models = result.all()
        serialized = [self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, m) for m in models]
        return serialized if include_secret else [_redact_model_secrets(model) for model in serialized]

    async def create_embedding_model(
        self, context: TenantContext, model_data: dict, preserve_uuid: bool = False
    ) -> str:
        """Create a new embedding model"""
        model_data = model_data.copy()
        if not preserve_uuid:
            model_data['uuid'] = str(uuid.uuid4())
        model_data['workspace_uuid'] = require_workspace_uuid(context)
        if 'extra_args' in model_data:
            model_data['extra_args'] = restore_secret_placeholders(model_data['extra_args'])

        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    context,
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await _require_workspace_provider(self.ap, context, model_data['provider_uuid'])
        await _validate_provider_supports(self.ap, context, model_data['provider_uuid'], 'text-embedding')

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.EmbeddingModel).values(**model_data)
        )

        runtime_provider = await _require_runtime_provider(self.ap, context, model_data['provider_uuid'])
        runtime_embedding_model = await self.ap.model_mgr.load_embedding_model_with_provider(
            context,
            persistence_model.EmbeddingModel(**model_data),
            runtime_provider,
        )
        await self.ap.model_mgr.cache_embedding_model(context, runtime_embedding_model)

        return model_data['uuid']

    async def get_embedding_model(
        self,
        context: TenantContext,
        model_uuid: str,
        include_secret: bool = False,
    ) -> dict | None:
        """Get a single embedding model with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.EmbeddingModel).where(
                    persistence_model.EmbeddingModel.uuid == model_uuid
                ),
                persistence_model.EmbeddingModel,
                context,
            )
        )
        model = result.first()
        if model is None:
            return None

        model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.EmbeddingModel, model)

        provider_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == model.provider_uuid
                ),
                persistence_model.ModelProvider,
                context,
            )
        )
        provider = provider_result.first()
        if provider:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
            provider_dict = _parse_provider_api_keys(provider_dict)
            model_dict['provider'] = provider_dict

        if not include_secret:
            model_dict = _redact_model_secrets(model_dict)

        return model_dict

    async def update_embedding_model(self, context: TenantContext, model_uuid: str, model_data: dict) -> None:
        """Update an existing embedding model"""
        existing_model = await self.get_embedding_model(context, model_uuid, include_secret=True)
        if existing_model is None:
            raise WorkspaceNotFoundError('Model not found')
        model_data = model_data.copy()
        model_data.pop('uuid', None)
        model_data.pop('workspace_uuid', None)
        if 'extra_args' in model_data:
            model_data['extra_args'] = restore_secret_placeholders(
                model_data['extra_args'],
                existing_model.get('extra_args', {}),
            )

        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    context,
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        provider_uuid = model_data.get('provider_uuid', existing_model['provider_uuid'])
        await _require_workspace_provider(self.ap, context, provider_uuid)
        await _validate_provider_supports(self.ap, context, provider_uuid, 'text-embedding')

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_model.EmbeddingModel)
                .where(persistence_model.EmbeddingModel.uuid == model_uuid)
                .values(**model_data),
                persistence_model.EmbeddingModel,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Model not found')

        await self.ap.model_mgr.remove_embedding_model(context, model_uuid)
        runtime_provider = await _require_runtime_provider(self.ap, context, provider_uuid)
        runtime_embedding_model = await self.ap.model_mgr.load_embedding_model_with_provider(
            context,
            persistence_model.EmbeddingModel(
                **_runtime_model_data(
                    model_uuid,
                    {
                        key: value
                        for key, value in {**existing_model, **model_data, 'provider_uuid': provider_uuid}.items()
                        if key not in {'provider', 'created_at', 'updated_at'}
                    },
                )
            ),
            runtime_provider,
        )
        await self.ap.model_mgr.cache_embedding_model(context, runtime_embedding_model)

    async def delete_embedding_model(self, context: TenantContext, model_uuid: str) -> None:
        """Delete an embedding model"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_model.EmbeddingModel).where(
                    persistence_model.EmbeddingModel.uuid == model_uuid
                ),
                persistence_model.EmbeddingModel,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Model not found')
        await self.ap.model_mgr.remove_embedding_model(context, model_uuid)

    async def test_embedding_model(self, context: TenantContext, model_uuid: str, model_data: dict) -> None:
        """Test an embedding model"""
        require_workspace_uuid(context)
        runtime_embedding_model: model_requester.RuntimeEmbeddingModel | None = None

        if model_uuid != '_':
            if await self.get_embedding_model(context, model_uuid) is None:
                raise WorkspaceNotFoundError('Model not found')
            runtime_embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(context, model_uuid)
        else:
            runtime_embedding_model = await self.ap.model_mgr.init_temporary_runtime_embedding_model(
                context,
                model_data,
            )

        await runtime_embedding_model.provider.invoke_embedding(
            model=runtime_embedding_model,
            input_text=['Hello, world!'],
            extra_args={},
            execution_context=runtime_embedding_model.execution_context,
        )


class RerankModelsService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_rerank_models(self, context: TenantContext, include_secret: bool = False) -> list[dict]:
        """Get all rerank models with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(persistence_model.RerankModel), persistence_model.RerankModel, context)
        )
        models = result.all()

        providers_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider), persistence_model.ModelProvider, context
            )
        )
        providers = {p.uuid: p for p in providers_result.all()}

        models_list = []
        for model in models:
            model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.RerankModel, model)
            provider = providers.get(model.provider_uuid)
            if provider:
                provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
                provider_dict = _parse_provider_api_keys(provider_dict)
                model_dict['provider'] = provider_dict
            if not include_secret:
                model_dict = _redact_model_secrets(model_dict)
            models_list.append(model_dict)

        return models_list

    async def get_rerank_models_by_provider(
        self,
        context: TenantContext,
        provider_uuid: str,
        *,
        include_secret: bool = False,
    ) -> list[dict]:
        """Get rerank models by provider UUID"""
        await _require_workspace_provider(self.ap, context, provider_uuid)
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.RerankModel).where(
                    persistence_model.RerankModel.provider_uuid == provider_uuid
                ),
                persistence_model.RerankModel,
                context,
            )
        )
        models = result.all()
        serialized = [self.ap.persistence_mgr.serialize_model(persistence_model.RerankModel, m) for m in models]
        return serialized if include_secret else [_redact_model_secrets(model) for model in serialized]

    async def create_rerank_model(self, context: TenantContext, model_data: dict, preserve_uuid: bool = False) -> str:
        """Create a new rerank model"""
        model_data = model_data.copy()
        if not preserve_uuid:
            model_data['uuid'] = str(uuid.uuid4())
        model_data['workspace_uuid'] = require_workspace_uuid(context)
        if 'extra_args' in model_data:
            model_data['extra_args'] = restore_secret_placeholders(model_data['extra_args'])

        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    context,
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        await _require_workspace_provider(self.ap, context, model_data['provider_uuid'])
        await _validate_provider_supports(self.ap, context, model_data['provider_uuid'], 'rerank')

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.RerankModel).values(**model_data)
        )

        runtime_provider = await _require_runtime_provider(self.ap, context, model_data['provider_uuid'])
        runtime_rerank_model = await self.ap.model_mgr.load_rerank_model_with_provider(
            context,
            persistence_model.RerankModel(**model_data),
            runtime_provider,
        )
        await self.ap.model_mgr.cache_rerank_model(context, runtime_rerank_model)

        return model_data['uuid']

    async def get_rerank_model(
        self,
        context: TenantContext,
        model_uuid: str,
        include_secret: bool = False,
    ) -> dict | None:
        """Get a single rerank model with provider info"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.RerankModel).where(
                    persistence_model.RerankModel.uuid == model_uuid
                ),
                persistence_model.RerankModel,
                context,
            )
        )
        model = result.first()
        if model is None:
            return None

        model_dict = self.ap.persistence_mgr.serialize_model(persistence_model.RerankModel, model)

        provider_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == model.provider_uuid
                ),
                persistence_model.ModelProvider,
                context,
            )
        )
        provider = provider_result.first()
        if provider:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
            provider_dict = _parse_provider_api_keys(provider_dict)
            model_dict['provider'] = provider_dict

        if not include_secret:
            model_dict = _redact_model_secrets(model_dict)

        return model_dict

    async def update_rerank_model(self, context: TenantContext, model_uuid: str, model_data: dict) -> None:
        """Update an existing rerank model"""
        existing_model = await self.get_rerank_model(context, model_uuid, include_secret=True)
        if existing_model is None:
            raise WorkspaceNotFoundError('Model not found')
        model_data = model_data.copy()
        model_data.pop('uuid', None)
        model_data.pop('workspace_uuid', None)
        if 'extra_args' in model_data:
            model_data['extra_args'] = restore_secret_placeholders(
                model_data['extra_args'],
                existing_model.get('extra_args', {}),
            )

        if 'provider' in model_data:
            provider_data = model_data.pop('provider')
            if provider_data.get('uuid'):
                model_data['provider_uuid'] = provider_data['uuid']
            else:
                provider_uuid = await self.ap.provider_service.find_or_create_provider(
                    context,
                    requester=provider_data.get('requester', ''),
                    base_url=provider_data.get('base_url', ''),
                    api_keys=provider_data.get('api_keys', []),
                )
                model_data['provider_uuid'] = provider_uuid

        provider_uuid = model_data.get('provider_uuid', existing_model['provider_uuid'])
        await _require_workspace_provider(self.ap, context, provider_uuid)
        await _validate_provider_supports(self.ap, context, provider_uuid, 'rerank')

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_model.RerankModel)
                .where(persistence_model.RerankModel.uuid == model_uuid)
                .values(**model_data),
                persistence_model.RerankModel,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Model not found')

        await self.ap.model_mgr.remove_rerank_model(context, model_uuid)
        runtime_provider = await _require_runtime_provider(self.ap, context, provider_uuid)
        runtime_rerank_model = await self.ap.model_mgr.load_rerank_model_with_provider(
            context,
            persistence_model.RerankModel(
                **_runtime_model_data(
                    model_uuid,
                    {
                        key: value
                        for key, value in {**existing_model, **model_data, 'provider_uuid': provider_uuid}.items()
                        if key not in {'provider', 'created_at', 'updated_at'}
                    },
                )
            ),
            runtime_provider,
        )
        await self.ap.model_mgr.cache_rerank_model(context, runtime_rerank_model)

    async def delete_rerank_model(self, context: TenantContext, model_uuid: str) -> None:
        """Delete a rerank model"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_model.RerankModel).where(
                    persistence_model.RerankModel.uuid == model_uuid
                ),
                persistence_model.RerankModel,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Model not found')
        await self.ap.model_mgr.remove_rerank_model(context, model_uuid)

    async def test_rerank_model(self, context: TenantContext, model_uuid: str, model_data: dict) -> None:
        """Test a rerank model"""
        require_workspace_uuid(context)
        runtime_rerank_model: model_requester.RuntimeRerankModel | None = None

        if model_uuid != '_':
            if await self.get_rerank_model(context, model_uuid) is None:
                raise WorkspaceNotFoundError('Model not found')
            runtime_rerank_model = await self.ap.model_mgr.get_rerank_model_by_uuid(context, model_uuid)
        else:
            runtime_rerank_model = await self.ap.model_mgr.init_temporary_runtime_rerank_model(
                context,
                model_data,
            )

        await runtime_rerank_model.provider.invoke_rerank(
            model=runtime_rerank_model,
            query='What is artificial intelligence?',
            documents=[
                'Artificial intelligence is a branch of computer science.',
                'The weather is nice today.',
            ],
            execution_context=runtime_rerank_model.execution_context,
        )
