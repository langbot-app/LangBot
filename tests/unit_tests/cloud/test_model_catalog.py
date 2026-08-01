from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.cloud.model_catalog import (
    CloudModelCatalogSnapshot,
    CloudModelCatalogSyncService,
    system_model_uuid,
    system_provider_uuid,
)
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.model import EmbeddingModel, LLMModel, ModelProvider
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode


pytestmark = pytest.mark.asyncio
INSTANCE_UUID = 'instance-model-catalog'
WORKSPACE_A = '00000000-0000-4000-8000-000000000001'
WORKSPACE_B = '00000000-0000-4000-8000-000000000002'
OWNER_A = '10000000-0000-4000-8000-000000000001'
OWNER_B = '10000000-0000-4000-8000-000000000002'


class _CatalogProvider:
    def __init__(self, snapshot: CloudModelCatalogSnapshot) -> None:
        self.snapshot = snapshot

    async def fetch_model_catalog(self, instance_uuid: str) -> CloudModelCatalogSnapshot:
        assert instance_uuid == INSTANCE_UUID
        return self.snapshot


def _snapshot(
    *,
    key_a: str | None = 'owner-a-key',
    model_id: str = 'gpt-test',
    include_embedding: bool = True,
) -> CloudModelCatalogSnapshot:
    models = [
        {
            'uuid': 'upstream-chat',
            'model_id': model_id,
            'category': 'chat',
            'llm_abilities': ['chat', 'vision'],
            'is_featured': True,
            'featured_order': 7,
        }
    ]
    if include_embedding:
        models.append(
            {
                'uuid': 'upstream-embedding',
                'model_id': 'embedding-test',
                'category': 'embedding',
            }
        )
    return CloudModelCatalogSnapshot.model_validate(
        {
            'instance_uuid': INSTANCE_UUID,
            'generated_at': datetime.now(UTC),
            'base_url': 'https://api.langbot.cloud/v1/',
            'models': models,
            'workspaces': [
                {
                    'workspace_uuid': WORKSPACE_A,
                    'owner_account_uuid': OWNER_A,
                    'api_key': key_a,
                },
                {
                    'workspace_uuid': WORKSPACE_B,
                    'owner_account_uuid': OWNER_B,
                    'api_key': 'owner-b-key',
                },
            ],
        }
    )


async def test_catalog_snapshot_treats_null_model_abilities_as_empty() -> None:
    payload = _snapshot().model_dump(mode='json')
    payload['models'][0]['llm_abilities'] = None

    snapshot = CloudModelCatalogSnapshot.model_validate(payload)

    assert snapshot.models[0].llm_abilities == ()


async def test_catalog_reconciles_every_workspace_idempotently_and_tracks_owner_and_downlisting(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "model-catalog.db"}')
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    bindings = [
        SimpleNamespace(instance_uuid=INSTANCE_UUID, workspace_uuid=WORKSPACE_A, placement_generation=1),
        SimpleNamespace(instance_uuid=INSTANCE_UUID, workspace_uuid=WORKSPACE_B, placement_generation=1),
    ]
    workspace_service = SimpleNamespace(list_active_execution_bindings=lambda: _async_value(bindings))
    reload_counter = _AsyncCounter()
    runtime_reload = SimpleNamespace(load_models_from_db=reload_counter)
    app = SimpleNamespace(
        persistence_mgr=manager,
        workspace_service=workspace_service,
        model_mgr=runtime_reload,
        logger=logging.getLogger(__name__),
    )
    provider = _CatalogProvider(_snapshot())
    service = CloudModelCatalogSyncService(app, provider, INSTANCE_UUID)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                sqlalchemy.insert(Workspace),
                [
                    {
                        'uuid': WORKSPACE_A,
                        'instance_uuid': INSTANCE_UUID,
                        'name': 'A',
                        'slug': 'a',
                        'source': 'cloud_projection',
                    },
                    {
                        'uuid': WORKSPACE_B,
                        'instance_uuid': INSTANCE_UUID,
                        'name': 'B',
                        'slug': 'b',
                        'source': 'cloud_projection',
                    },
                ],
            )
            await connection.execute(
                sqlalchemy.insert(ModelProvider).values(
                    uuid='custom-provider',
                    workspace_uuid=WORKSPACE_A,
                    name='Custom',
                    requester='openai-chat-completions',
                    base_url='https://custom.example/v1',
                    api_keys=['custom-key'],
                )
            )
            await connection.execute(
                sqlalchemy.insert(LLMModel).values(
                    uuid='custom-model',
                    workspace_uuid=WORKSPACE_A,
                    name='custom-model',
                    provider_uuid='custom-provider',
                    abilities=['chat'],
                    extra_args={},
                    prefered_ranking=0,
                )
            )

        first = await service.sync_once()
        assert first == {'workspaces': 2, 'created': 6, 'updated': 0, 'deleted': 0}
        assert reload_counter.calls == 1

        async with engine.connect() as connection:
            providers = (
                await connection.execute(
                    sqlalchemy.select(
                        ModelProvider.uuid,
                        ModelProvider.workspace_uuid,
                        ModelProvider.api_keys,
                    ).where(ModelProvider.requester == 'space-chat-completions')
                )
            ).all()
            assert {item.workspace_uuid for item in providers} == {WORKSPACE_A, WORKSPACE_B}
            assert {item.uuid for item in providers} == {
                system_provider_uuid(WORKSPACE_A),
                system_provider_uuid(WORKSPACE_B),
            }
            assert {item.workspace_uuid: item.api_keys for item in providers} == {
                WORKSPACE_A: ['owner-a-key'],
                WORKSPACE_B: ['owner-b-key'],
            }
            assert await connection.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(LLMModel)) == 3
            assert await connection.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(EmbeddingModel)) == 2

        second = await service.sync_once()
        assert second == {'workspaces': 2, 'created': 0, 'updated': 0, 'deleted': 0}
        assert reload_counter.calls == 1

        provider.snapshot = _snapshot(
            key_a='new-owner-key',
            model_id='gpt-renamed',
            include_embedding=False,
        )
        third = await service.sync_once()
        assert third == {'workspaces': 2, 'created': 0, 'updated': 3, 'deleted': 2}
        assert reload_counter.calls == 2

        async with engine.connect() as connection:
            provider_a_keys = await connection.scalar(
                sqlalchemy.select(ModelProvider.api_keys).where(ModelProvider.uuid == system_provider_uuid(WORKSPACE_A))
            )
            assert provider_a_keys == ['new-owner-key']
            system_model_names = (
                (
                    await connection.execute(
                        sqlalchemy.select(LLMModel.name).where(
                            LLMModel.provider_uuid.in_(
                                [system_provider_uuid(WORKSPACE_A), system_provider_uuid(WORKSPACE_B)]
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert set(system_model_names) == {'gpt-renamed'}
            assert await connection.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(EmbeddingModel)) == 0
            assert (
                await connection.scalar(
                    sqlalchemy.select(sqlalchemy.func.count())
                    .select_from(ModelProvider)
                    .where(ModelProvider.uuid == 'custom-provider')
                )
                == 1
            )
            assert (
                await connection.scalar(
                    sqlalchemy.select(sqlalchemy.func.count())
                    .select_from(LLMModel)
                    .where(LLMModel.uuid == 'custom-model')
                )
                == 1
            )

        provider.snapshot = _snapshot(key_a=None, model_id='gpt-renamed', include_embedding=False)
        fourth = await service.sync_once()
        assert fourth == {'workspaces': 2, 'created': 0, 'updated': 1, 'deleted': 0}
        assert reload_counter.calls == 3
        async with engine.connect() as connection:
            provider_a_keys = await connection.scalar(
                sqlalchemy.select(ModelProvider.api_keys).where(ModelProvider.uuid == system_provider_uuid(WORKSPACE_A))
            )
            assert provider_a_keys == []
    finally:
        await engine.dispose()


def test_workspace_scoped_ids_are_stable_and_secrets_are_redacted() -> None:
    assert system_provider_uuid(WORKSPACE_A) == system_provider_uuid(WORKSPACE_A)
    assert system_provider_uuid(WORKSPACE_A) != system_provider_uuid(WORKSPACE_B)
    assert system_model_uuid(WORKSPACE_A, 'chat', 'upstream') != system_model_uuid(WORKSPACE_B, 'chat', 'upstream')
    snapshot = _snapshot()
    assert 'owner-a-key' not in repr(snapshot)


async def test_snapshot_must_cover_every_active_workspace() -> None:
    snapshot = _snapshot().model_copy(update={'workspaces': _snapshot().workspaces[:1]})
    app = SimpleNamespace(
        workspace_service=SimpleNamespace(
            list_active_execution_bindings=lambda: _async_value(
                [SimpleNamespace(workspace_uuid=WORKSPACE_A), SimpleNamespace(workspace_uuid=WORKSPACE_B)]
            )
        ),
        logger=logging.getLogger(__name__),
    )
    service = CloudModelCatalogSyncService(app, _CatalogProvider(snapshot), INSTANCE_UUID)
    with pytest.raises(ValueError, match='missing billing projections for 1 active Workspaces'):
        await service.sync_once()


async def _async_value(value):
    return value


class _AsyncCounter:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1


async def test_partial_workspace_failure_reloads_already_committed_changes() -> None:
    bindings = [
        SimpleNamespace(workspace_uuid=WORKSPACE_A),
        SimpleNamespace(workspace_uuid=WORKSPACE_B),
    ]
    reload_counter = _AsyncCounter()
    app = SimpleNamespace(
        workspace_service=SimpleNamespace(list_active_execution_bindings=lambda: _async_value(bindings)),
        model_mgr=SimpleNamespace(load_models_from_db=reload_counter),
        logger=logging.getLogger(__name__),
    )
    service = CloudModelCatalogSyncService(app, _CatalogProvider(_snapshot()), INSTANCE_UUID)
    calls = 0

    async def sync_workspace(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {'created': 1, 'updated': 0, 'deleted': 0}
        raise RuntimeError('second Workspace failed')

    service._sync_workspace = sync_workspace  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match='second Workspace failed'):
        await service.sync_once()
    assert reload_counter.calls == 1


async def test_failed_runtime_reload_is_retried_after_noop_sync() -> None:
    bindings = [SimpleNamespace(workspace_uuid=WORKSPACE_A)]

    class _FlakyReload:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError('reload failed')

    runtime_reload = _FlakyReload()
    app = SimpleNamespace(
        workspace_service=SimpleNamespace(list_active_execution_bindings=lambda: _async_value(bindings)),
        model_mgr=SimpleNamespace(load_models_from_db=runtime_reload),
        logger=logging.getLogger(__name__),
    )
    service = CloudModelCatalogSyncService(app, _CatalogProvider(_snapshot()), INSTANCE_UUID)
    calls = 0

    async def sync_workspace(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {'created': 1, 'updated': 0, 'deleted': 0}
        return {'created': 0, 'updated': 0, 'deleted': 0}

    service._sync_workspace = sync_workspace  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match='reload failed'):
        await service.sync_once()
    summary = await service.sync_once()
    assert summary == {'workspaces': 1, 'created': 0, 'updated': 0, 'deleted': 0}
    assert runtime_reload.calls == 2


async def test_background_sync_log_redacts_exception_message(caplog) -> None:
    secret = 'owner-secret-api-key'
    attempted = asyncio.Event()

    class _FailingProvider:
        async def fetch_model_catalog(self, instance_uuid: str) -> CloudModelCatalogSnapshot:
            del instance_uuid
            attempted.set()
            raise RuntimeError(f'database parameters include {secret}')

    app = SimpleNamespace(logger=logging.getLogger(__name__))
    service = CloudModelCatalogSyncService(app, _FailingProvider(), INSTANCE_UUID)
    service.sync_interval_seconds = 0.001
    task = asyncio.create_task(service.run())
    try:
        await asyncio.wait_for(attempted.wait(), timeout=1)
        await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert secret not in caplog.text
    assert 'Cloud model catalog synchronization failed (RuntimeError)' in caplog.text
