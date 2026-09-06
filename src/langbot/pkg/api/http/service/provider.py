from __future__ import annotations

import asyncio
import uuid
import traceback

import sqlalchemy

from ....cloud.model_catalog import LANGBOT_MODELS_PROVIDER_REQUESTER
from ....core import app
from ....core.task_boundary import create_detached_task
from ....entity.persistence import model as persistence_model
from ....workspace.errors import WorkspaceNotFoundError
from ....provider.modelmgr.codex_auth import CodexAuth, REQUESTER as CODEX_REQUESTER, validate_config
from .secrets import contains_secret_placeholder, redact_secrets, restore_secret_placeholders
from .tenant import TenantContext, require_workspace_uuid, scope_statement


class ModelProviderService:
    """Service for managing model providers"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.codex_auth = CodexAuth(ap)
        self._deletion_tasks: set[asyncio.Task[None]] = set()

    def _is_cloud_runtime(self) -> bool:
        mode = getattr(self.ap.persistence_mgr, 'mode', None)
        return getattr(mode, 'value', None) == 'cloud_runtime'

    def _system_requester_is_reserved(self, requester: object) -> bool:
        return self._is_cloud_runtime() and requester == LANGBOT_MODELS_PROVIDER_REQUESTER

    async def _assert_provider_mutable(self, context: TenantContext, provider_uuid: str) -> None:
        if not self._is_cloud_runtime():
            return
        provider = await self.get_provider(context, provider_uuid)
        if provider is not None and self._system_requester_is_reserved(provider.get('requester')):
            raise ValueError('LangBot Models is managed by Cloud and cannot be modified')

    @staticmethod
    def _normalize_api_keys(api_keys: str | list[str] | tuple[str, ...] | None) -> list[str]:
        if api_keys is None:
            return []

        raw_keys = [api_keys] if isinstance(api_keys, str) else list(api_keys)
        normalized_keys = []
        seen_keys = set()

        for raw_key in raw_keys:
            normalized_key = raw_key.strip() if isinstance(raw_key, str) else ''
            if not normalized_key or normalized_key in seen_keys:
                continue
            normalized_keys.append(normalized_key)
            seen_keys.add(normalized_key)

        return normalized_keys

    async def get_providers(self, context: TenantContext, include_secret: bool = False) -> list[dict]:
        """Get all providers"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider),
                persistence_model.ModelProvider,
                context,
            )
        )
        providers = result.all()
        providers_list = []
        for p in providers:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, p)
            # Parse api_keys if it's a JSON string
            if isinstance(provider_dict.get('api_keys'), str):
                import json

                try:
                    provider_dict['api_keys'] = json.loads(provider_dict['api_keys'])
                except Exception:
                    provider_dict['api_keys'] = []
            if not include_secret:
                provider_dict = redact_secrets(provider_dict)
            providers_list.append(provider_dict)
        return providers_list

    async def get_provider(
        self,
        context: TenantContext,
        provider_uuid: str,
        include_secret: bool = False,
    ) -> dict | None:
        """Get a single provider by UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == provider_uuid
                ),
                persistence_model.ModelProvider,
                context,
            )
        )
        provider = result.first()
        if provider is None:
            return None
        provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
        # Parse api_keys if it's a JSON string
        if isinstance(provider_dict.get('api_keys'), str):
            import json

            try:
                provider_dict['api_keys'] = json.loads(provider_dict['api_keys'])
            except Exception:
                provider_dict['api_keys'] = []
        if not include_secret:
            provider_dict = redact_secrets(provider_dict)
        return provider_dict

    async def create_provider(self, context: TenantContext, provider_data: dict) -> str:
        """Create a new provider"""
        provider_data = provider_data.copy()
        if self._system_requester_is_reserved(provider_data.get('requester')):
            raise ValueError('space-chat-completions is reserved for the Cloud-managed LangBot Models provider')
        validate_config(provider_data)
        provider_data['uuid'] = str(uuid.uuid4())
        provider_data['workspace_uuid'] = require_workspace_uuid(context)
        provider_data['api_keys'] = self._normalize_api_keys(
            restore_secret_placeholders(provider_data.get('api_keys'), sensitive=True)
        )
        if provider_data.get('requester') == CODEX_REQUESTER:
            async with self.ap.persistence_mgr.tenant_uow(provider_data['workspace_uuid']):
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_model.ModelProvider).values(**provider_data)
                )
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_model.CodexCredential).values(
                        workspace_uuid=provider_data['workspace_uuid'],
                        provider_uuid=provider_data['uuid'],
                        payload={},
                        version=0,
                        lease_until=0,
                    )
                )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_model.ModelProvider).values(**provider_data)
            )

        # load to runtime
        runtime_provider = await self.ap.model_mgr.load_provider(context, provider_data)
        await self.ap.model_mgr.cache_provider(context, runtime_provider)
        return provider_data['uuid']

    async def update_provider(self, context: TenantContext, provider_uuid: str, provider_data: dict) -> None:
        """Update an existing provider"""
        await self._assert_provider_mutable(context, provider_uuid)
        provider_data = provider_data.copy()
        if self._system_requester_is_reserved(provider_data.get('requester')):
            raise ValueError('space-chat-completions is reserved for the Cloud-managed LangBot Models provider')
        provider_data.pop('uuid', None)
        provider_data.pop('workspace_uuid', None)
        if {'requester', 'base_url', 'api_keys'} & provider_data.keys():
            current = await self.get_provider(context, provider_uuid, include_secret=True)
            if current is None:
                raise WorkspaceNotFoundError('Provider not found')
            if CODEX_REQUESTER in (current.get('requester'), provider_data.get('requester')):
                if provider_data.get('requester', current.get('requester')) != current.get('requester'):
                    raise ValueError('Create a separate provider to change the ChatGPT authentication type')
                merged = {**current, **provider_data}
                validate_config(merged)
                provider_data['base_url'] = merged['base_url']
                provider_data['api_keys'] = []
        if 'api_keys' in provider_data:
            submitted_keys = provider_data.get('api_keys')
            if contains_secret_placeholder(submitted_keys, sensitive=True):
                current_provider = await self.get_provider(context, provider_uuid, include_secret=True)
                if current_provider is None:
                    raise WorkspaceNotFoundError('Provider not found')
                submitted_keys = restore_secret_placeholders(
                    submitted_keys,
                    current_provider.get('api_keys', []),
                    sensitive=True,
                )
            provider_data['api_keys'] = self._normalize_api_keys(submitted_keys)
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_model.ModelProvider)
                .where(persistence_model.ModelProvider.uuid == provider_uuid)
                .values(**provider_data),
                persistence_model.ModelProvider,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Provider not found')
        await self.ap.model_mgr.reload_provider(context, provider_uuid)

    async def delete_provider(self, context: TenantContext, provider_uuid: str, cascade: bool = False) -> None:
        """Delete a provider, optionally deleting all its Workspace-scoped models."""
        workspace_uuid = require_workspace_uuid(context)
        persistence = self.ap.persistence_mgr
        model_types = (
            (persistence_model.LLMModel, 'LLM', 'remove_llm_model'),
            (persistence_model.EmbeddingModel, 'Embedding', 'remove_embedding_model'),
            (persistence_model.RerankModel, 'Rerank', 'remove_rerank_model'),
        )
        deleted_models: list[tuple[str, list[str]]] = []
        async with persistence.tenant_uow(workspace_uuid):
            # Check ownership before touching children. Lock the provider on PostgreSQL
            # so concurrent model inserts cannot race the reference check/deletion.
            provider_result = await persistence.execute_async(
                scope_statement(
                    sqlalchemy.select(persistence_model.ModelProvider.requester)
                    .where(persistence_model.ModelProvider.uuid == provider_uuid)
                    .with_for_update(),
                    persistence_model.ModelProvider,
                    workspace_uuid,
                )
            )
            provider = provider_result.first()
            if provider is None:
                raise WorkspaceNotFoundError('Provider not found')
            if self._system_requester_is_reserved(provider.requester):
                raise ValueError('LangBot Models is managed by Cloud and cannot be modified')

            for model_type, label, remover in model_types:
                result = await persistence.execute_async(
                    scope_statement(
                        sqlalchemy.select(model_type.uuid).where(model_type.provider_uuid == provider_uuid),
                        model_type,
                        workspace_uuid,
                    )
                )
                model_uuids = list(result.scalars())
                if model_uuids and not cascade:
                    raise ValueError(f'Cannot delete provider: {label} models still reference it')
                if model_uuids:
                    # Model services have no pipeline/KB deletion side effects: they
                    # delete the scoped row and evict its runtime cache. Defer eviction
                    # here rather than calling those services before our commit.
                    await persistence.execute_async(
                        scope_statement(
                            sqlalchemy.delete(model_type).where(model_type.provider_uuid == provider_uuid),
                            model_type,
                            workspace_uuid,
                        )
                    )
                    deleted_models.append((remover, model_uuids))

            # Explicit cleanup also works on legacy SQLite connections without FK
            # enforcement; never load or serialize the private credential payload.
            await persistence.execute_async(
                scope_statement(
                    sqlalchemy.delete(persistence_model.CodexCredential).where(
                        persistence_model.CodexCredential.provider_uuid == provider_uuid
                    ),
                    persistence_model.CodexCredential,
                    workspace_uuid,
                )
            )
            result = await persistence.execute_async(
                scope_statement(
                    sqlalchemy.delete(persistence_model.ModelProvider).where(
                        persistence_model.ModelProvider.uuid == provider_uuid
                    ),
                    persistence_model.ModelProvider,
                    workspace_uuid,
                )
            )
            if result.rowcount == 0:
                raise WorkspaceNotFoundError('Provider not found')

        async def remove_runtime() -> None:
            async with persistence.tenant_scope(workspace_uuid):
                for remover, model_uuids in deleted_models:
                    for model_uuid in model_uuids:
                        await getattr(self.ap.model_mgr, remover)(context, model_uuid)
                # This also closes the requester's HTTP client; models go first.
                await self.ap.model_mgr.remove_provider(context, provider_uuid)

        if persistence.current_session() is None:
            await remove_runtime()
        else:
            # A nested UoW has not committed yet. Reuse the rollback-cancelled gate
            # and detached context boundary instead of evicting uncommitted data.
            task = create_detached_task(
                remove_runtime(),
                after_commit_manager=persistence,
                workspace_uuid=workspace_uuid,
            )
            self._deletion_tasks.add(task)

            def completed(task: asyncio.Task[None]) -> None:
                self._deletion_tasks.discard(task)
                if not task.cancelled() and task.exception() is not None:
                    self.ap.logger.error('Failed to remove deleted provider runtime', exc_info=task.exception())

            task.add_done_callback(completed)

    async def get_provider_model_counts(self, context: TenantContext, provider_uuid: str) -> dict:
        """Get count of models using this provider"""
        workspace_uuid = require_workspace_uuid(context)
        if await self.get_provider(context, provider_uuid) is None:
            raise WorkspaceNotFoundError('Provider not found')
        llm_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(persistence_model.LLMModel)
                .where(persistence_model.LLMModel.provider_uuid == provider_uuid),
                persistence_model.LLMModel,
                workspace_uuid,
            )
        )
        llm_count = llm_result.scalar() or 0

        embedding_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(persistence_model.EmbeddingModel)
                .where(persistence_model.EmbeddingModel.provider_uuid == provider_uuid),
                persistence_model.EmbeddingModel,
                workspace_uuid,
            )
        )
        embedding_count = embedding_result.scalar() or 0

        rerank_result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(persistence_model.RerankModel)
                .where(persistence_model.RerankModel.provider_uuid == provider_uuid),
                persistence_model.RerankModel,
                workspace_uuid,
            )
        )
        rerank_count = rerank_result.scalar() or 0

        return {'llm_count': llm_count, 'embedding_count': embedding_count, 'rerank_count': rerank_count}

    async def find_or_create_provider(
        self,
        context: TenantContext,
        requester: str,
        base_url: str,
        api_keys: list,
    ) -> str:
        """Find existing provider or create new one"""
        if self._system_requester_is_reserved(requester):
            raise ValueError('space-chat-completions is reserved for the Cloud-managed LangBot Models provider')
        workspace_uuid = require_workspace_uuid(context)
        api_keys = self._normalize_api_keys(restore_secret_placeholders(api_keys, sensitive=True))

        # Try to find existing provider with same config
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.requester == requester,
                    persistence_model.ModelProvider.base_url == base_url,
                ),
                persistence_model.ModelProvider,
                workspace_uuid,
            )
        )
        for provider in result.all():
            if sorted(provider.api_keys or []) == sorted(api_keys or []):
                return provider.uuid

        # Create new provider
        provider_name = requester
        if base_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(base_url)
                provider_name = parsed.netloc or requester
            except Exception:
                pass

        return await self.create_provider(
            context,
            {
                'name': provider_name,
                'requester': requester,
                'base_url': base_url,
                'api_keys': api_keys,
            },
        )

    async def update_space_model_provider_api_keys(self, context: TenantContext, api_key: str) -> None:
        """Update Space model provider API keys"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_model.ModelProvider)
                .where(persistence_model.ModelProvider.uuid == '00000000-0000-0000-0000-000000000000')
                .values(api_keys=self._normalize_api_keys(api_key)),
                persistence_model.ModelProvider,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Provider not found')
        await self.ap.model_mgr.reload_provider(context, '00000000-0000-0000-0000-000000000000')

    async def scan_provider_models(
        self, context: TenantContext, provider_uuid: str, model_type: str | None = None
    ) -> dict:
        provider = await self.get_provider(context, provider_uuid, include_secret=True)
        if provider is None:
            raise WorkspaceNotFoundError('Provider not found')

        runtime_provider = await self.ap.model_mgr.load_provider(context, provider)

        try:
            scan_result = await runtime_provider.requester.scan_models(
                runtime_provider.token_mgr.get_token() if runtime_provider.token_mgr.tokens else None
            )
        except NotImplementedError:
            raise ValueError('current provider does not support model scanning')
        except Exception as exc:
            self.ap.logger.warning(
                f'Failed to scan models for provider {provider_uuid}: {exc}\n{traceback.format_exc()}'
            )
            raise ValueError(str(exc)) from exc

        if isinstance(scan_result, dict):
            scanned_models = scan_result.get('models', [])
            debug_info = scan_result.get('debug')
        else:
            scanned_models = scan_result
            debug_info = None

        llm_models = await self.ap.llm_model_service.get_llm_models_by_provider(context, provider_uuid)
        embedding_models = await self.ap.embedding_models_service.get_embedding_models_by_provider(
            context, provider_uuid
        )
        rerank_service = getattr(self.ap, 'rerank_models_service', None)
        rerank_models = (
            await rerank_service.get_rerank_models_by_provider(context, provider_uuid)
            if rerank_service is not None
            else []
        )
        existing_llm_names = {model['name'] for model in llm_models}
        existing_embedding_names = {model['name'] for model in embedding_models}
        existing_rerank_names = {model['name'] for model in rerank_models}

        filtered_models = []
        for model in scanned_models:
            scanned_type = model.get('type', 'llm')
            if model_type and scanned_type != model_type:
                continue

            model_name = model.get('name') or model.get('id')
            if not model_name:
                continue

            filtered_models.append(
                {
                    'id': model.get('id', model_name),
                    'name': model_name,
                    'type': scanned_type,
                    'abilities': model.get('abilities', []),
                    'display_name': model.get('display_name'),
                    'description': model.get('description'),
                    'context_length': model.get('context_length'),
                    'owned_by': model.get('owned_by'),
                    'input_modalities': model.get('input_modalities', []),
                    'output_modalities': model.get('output_modalities', []),
                    'already_added': (
                        model_name in existing_embedding_names
                        if scanned_type == 'embedding'
                        else model_name in existing_rerank_names
                        if scanned_type == 'rerank'
                        else model_name in existing_llm_names
                    ),
                }
            )

        return {'models': filtered_models, 'debug': debug_info}
