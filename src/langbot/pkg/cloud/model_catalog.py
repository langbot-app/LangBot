from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

import sqlalchemy
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from ..entity.persistence import model as persistence_model


LANGBOT_MODELS_PROVIDER_REQUESTER = 'space-chat-completions'
LANGBOT_MODELS_PROVIDER_NAME = 'LangBot Models'
_MODEL_RESOURCE_NAMESPACE = uuid.UUID('94c703ca-1df5-4e91-bcd3-74ac65cb7921')
_SUPPORTED_CATEGORIES = {'chat', 'embedding', 'rerank'}
_MODEL_TABLES = (
    persistence_model.LLMModel,
    persistence_model.EmbeddingModel,
    persistence_model.RerankModel,
)


class CloudModelCatalogItem(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    uuid: str = Field(min_length=1, max_length=255)
    model_id: str = Field(min_length=1, max_length=255)
    category: Literal['chat', 'embedding', 'rerank']
    llm_abilities: tuple[str, ...] = ()
    is_featured: bool = False
    featured_order: int = 0

    @field_validator('llm_abilities', mode='before')
    @classmethod
    def normalize_missing_abilities(cls, value: Any) -> Any:
        return () if value is None else value

    @field_validator('llm_abilities')
    @classmethod
    def validate_abilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 64 for item in value):
            raise ValueError('Model abilities must be non-empty strings of at most 64 characters')
        if len(set(value)) != len(value):
            raise ValueError('Model abilities must be unique')
        return value


class CloudWorkspaceModelBilling(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    workspace_uuid: str = Field(min_length=36, max_length=36)
    owner_account_uuid: str | None = Field(default=None, min_length=36, max_length=36)
    api_key: SecretStr | None = None

    @field_validator('workspace_uuid')
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator('owner_account_uuid')
    @classmethod
    def validate_optional_uuid(cls, value: str | None) -> str | None:
        return None if value is None else str(uuid.UUID(value))


class CloudModelCatalogSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    instance_uuid: str = Field(min_length=1, max_length=255)
    generated_at: datetime
    base_url: str = Field(min_length=1, max_length=512)
    models: tuple[CloudModelCatalogItem, ...]
    workspaces: tuple[CloudWorkspaceModelBilling, ...]

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.rstrip('/')
        if not normalized.startswith('https://'):
            raise ValueError('Cloud model gateway base URL must use HTTPS')
        return normalized

    @field_validator('models')
    @classmethod
    def validate_models(cls, value: tuple[CloudModelCatalogItem, ...]) -> tuple[CloudModelCatalogItem, ...]:
        if len(value) > 500:
            raise ValueError('Cloud model catalog exceeds 500 models')
        identities = {(item.category, item.uuid) for item in value}
        if len(identities) != len(value):
            raise ValueError('Cloud model catalog contains duplicate model identities')
        return value

    @field_validator('workspaces')
    @classmethod
    def validate_workspaces(
        cls, value: tuple[CloudWorkspaceModelBilling, ...]
    ) -> tuple[CloudWorkspaceModelBilling, ...]:
        if len(value) > 10_000:
            raise ValueError('Cloud model catalog exceeds 10000 Workspaces')
        identities = {item.workspace_uuid for item in value}
        if len(identities) != len(value):
            raise ValueError('Cloud model catalog contains duplicate Workspaces')
        return value


@runtime_checkable
class CloudModelCatalogProvider(Protocol):
    async def fetch_model_catalog(self, instance_uuid: str) -> CloudModelCatalogSnapshot:
        """Fetch and verify the complete model catalog and Workspace billing projection."""
        ...


def system_provider_uuid(workspace_uuid: str) -> str:
    workspace = str(uuid.UUID(workspace_uuid))
    return str(uuid.uuid5(_MODEL_RESOURCE_NAMESPACE, f'{workspace}:provider:{LANGBOT_MODELS_PROVIDER_REQUESTER}'))


def system_model_uuid(workspace_uuid: str, category: str, upstream_uuid: str) -> str:
    workspace = str(uuid.UUID(workspace_uuid))
    if category not in _SUPPORTED_CATEGORIES:
        raise ValueError(f'Unsupported model category: {category}')
    if not upstream_uuid:
        raise ValueError('Upstream model UUID is required')
    return str(uuid.uuid5(_MODEL_RESOURCE_NAMESPACE, f'{workspace}:model:{category}:{upstream_uuid}'))


class CloudModelCatalogSyncService:
    """Reconcile Space-owned model catalog and Owner billing tokens into every Cloud Workspace."""

    def __init__(
        self,
        ap: Any,
        provider: CloudModelCatalogProvider,
        instance_uuid: str,
        *,
        sync_interval_seconds: float = 3600.0,
    ) -> None:
        if not isinstance(provider, CloudModelCatalogProvider):
            raise TypeError('Cloud model catalog sync requires a CloudModelCatalogProvider')
        if sync_interval_seconds < 10:
            raise ValueError('Cloud model catalog sync interval must be at least 10 seconds')
        self.ap = ap
        self.provider = provider
        self.instance_uuid = instance_uuid
        self.sync_interval_seconds = float(sync_interval_seconds)
        # A tenant UoW commits one Workspace at a time. Keep a durable in-memory
        # convergence marker so a failed runtime reload is retried even when the
        # following database reconciliation is a no-op.
        self._runtime_reload_pending = False

    async def initialize(self) -> None:
        await self.sync_once(reload_runtime=False)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.sync_interval_seconds)
            try:
                await self.sync_once(reload_runtime=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Exception messages can contain rendered SQL bound values,
                # including provider API keys. Log only the exception class.
                self.ap.logger.warning(f'Cloud model catalog synchronization failed ({type(exc).__name__})')

    async def sync_once(self, *, reload_runtime: bool = True) -> dict[str, int]:
        summary = {'workspaces': 0, 'created': 0, 'updated': 0, 'deleted': 0}
        snapshot: CloudModelCatalogSnapshot | None = None
        sync_error: Exception | None = None
        reload_error: Exception | None = None
        try:
            snapshot = await self.provider.fetch_model_catalog(self.instance_uuid)
            if snapshot.instance_uuid != self.instance_uuid:
                raise ValueError('Cloud model catalog targets another LangBot instance')

            bindings = await self.ap.workspace_service.list_active_execution_bindings()
            billing_by_workspace = {item.workspace_uuid: item for item in snapshot.workspaces}
            missing = sorted(
                binding.workspace_uuid for binding in bindings if binding.workspace_uuid not in billing_by_workspace
            )
            if missing:
                raise ValueError(
                    f'Cloud model catalog is missing billing projections for {len(missing)} active Workspaces'
                )

            for binding in bindings:
                counts = await self._sync_workspace(
                    binding.workspace_uuid,
                    snapshot,
                    billing_by_workspace[binding.workspace_uuid],
                )
                summary['workspaces'] += 1
                workspace_changed = any(counts[key] > 0 for key in ('created', 'updated', 'deleted'))
                if workspace_changed:
                    # _sync_workspace returns only after its tenant UoW commits.
                    self._runtime_reload_pending = True
                for key in ('created', 'updated', 'deleted'):
                    summary[key] += counts[key]
        except Exception as exc:
            sync_error = exc
        finally:
            model_mgr = getattr(self.ap, 'model_mgr', None)
            if reload_runtime and self._runtime_reload_pending and model_mgr is not None:
                try:
                    await model_mgr.load_models_from_db()
                except Exception as exc:
                    reload_error = exc
                else:
                    self._runtime_reload_pending = False

        if sync_error is not None:
            if reload_error is not None:
                raise sync_error from reload_error
            raise sync_error
        if reload_error is not None:
            raise reload_error

        changed = any(summary[key] > 0 for key in ('created', 'updated', 'deleted'))
        if changed and snapshot is not None:
            self.ap.logger.info(
                'Cloud model catalog synchronized '
                f'({summary["workspaces"]} Workspaces, {len(snapshot.models)} models, '
                f'created={summary["created"]}, updated={summary["updated"]}, deleted={summary["deleted"]})'
            )
        return summary

    async def _sync_workspace(
        self,
        workspace_uuid: str,
        snapshot: CloudModelCatalogSnapshot,
        billing: CloudWorkspaceModelBilling,
    ) -> dict[str, int]:
        counts = {'created': 0, 'updated': 0, 'deleted': 0}
        provider_uuid = system_provider_uuid(workspace_uuid)
        desired_keys = [billing.api_key.get_secret_value()] if billing.api_key is not None else []

        async with self.ap.persistence_mgr.tenant_uow(workspace_uuid) as uow:
            provider = await uow.session.scalar(
                sqlalchemy.select(persistence_model.ModelProvider).where(
                    persistence_model.ModelProvider.uuid == provider_uuid
                )
            )
            provider_values = {
                'workspace_uuid': workspace_uuid,
                'name': LANGBOT_MODELS_PROVIDER_NAME,
                'requester': LANGBOT_MODELS_PROVIDER_REQUESTER,
                'base_url': snapshot.base_url,
                'api_keys': desired_keys,
            }
            if provider is None:
                provider = persistence_model.ModelProvider(uuid=provider_uuid, **provider_values)
                uow.session.add(provider)
                await uow.session.flush()
                counts['created'] += 1
            elif self._update_entity(provider, provider_values):
                counts['updated'] += 1

            existing_by_table: dict[type, dict[str, Any]] = {}
            for table in _MODEL_TABLES:
                rows = (
                    await uow.session.scalars(sqlalchemy.select(table).where(table.provider_uuid == provider_uuid))
                ).all()
                existing_by_table[table] = {row.uuid: row for row in rows}

            desired_ids: dict[type, set[str]] = {table: set() for table in _MODEL_TABLES}
            for item in snapshot.models:
                table, values = self._model_values(workspace_uuid, provider_uuid, item)
                model_uuid = system_model_uuid(workspace_uuid, item.category, item.uuid)
                desired_ids[table].add(model_uuid)
                existing = existing_by_table[table].get(model_uuid)
                if existing is None:
                    uow.session.add(table(uuid=model_uuid, **values))
                    counts['created'] += 1
                elif self._update_entity(existing, values):
                    counts['updated'] += 1

            for table, entities in existing_by_table.items():
                for model_uuid, entity in entities.items():
                    if model_uuid not in desired_ids[table]:
                        await uow.session.delete(entity)
                        counts['deleted'] += 1

        return counts

    @staticmethod
    def _update_entity(entity: Any, values: dict[str, Any]) -> bool:
        changed = False
        for key, value in values.items():
            if getattr(entity, key) != value:
                setattr(entity, key, value)
                changed = True
        return changed

    @staticmethod
    def _model_values(
        workspace_uuid: str,
        provider_uuid: str,
        item: CloudModelCatalogItem,
    ) -> tuple[type, dict[str, Any]]:
        ranking = 100 - item.featured_order if item.is_featured else 0
        common = {
            'workspace_uuid': workspace_uuid,
            'name': item.model_id,
            'provider_uuid': provider_uuid,
            'extra_args': {},
            'prefered_ranking': ranking,
        }
        if item.category == 'chat':
            return persistence_model.LLMModel, {
                **common,
                'abilities': list(item.llm_abilities),
                'context_length': None,
            }
        if item.category == 'embedding':
            return persistence_model.EmbeddingModel, common
        if item.category == 'rerank':
            return persistence_model.RerankModel, common
        raise ValueError(f'Unsupported model category: {item.category}')
