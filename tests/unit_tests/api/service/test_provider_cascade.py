"""Provider deletion uses real SQLite transactions and real runtime cache cleanup."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
import quart
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.controller.groups.provider.providers import ModelProvidersRouterGroup
from langbot.pkg.api.http.service.provider import ModelProviderService
from langbot.pkg.entity.persistence.model import CodexCredential, EmbeddingModel, LLMModel, ModelProvider, RerankModel
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.workspace.errors import WorkspaceNotFoundError

pytestmark = pytest.mark.asyncio
MODEL_TYPES = (LLMModel, EmbeddingModel, RerankModel)
TABLES = (*MODEL_TYPES, CodexCredential, ModelProvider)


@pytest_asyncio.fixture
async def deletion(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "cascade.db"}')

    @sa.event.listens_for(engine.sync_engine, 'connect')
    def enable_foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')

    ap = SimpleNamespace(logger=Mock())
    pm = ap.persistence_mgr = PersistenceManager(ap)
    pm.db = SimpleNamespace(get_engine=lambda: engine)
    manager = ap.model_mgr = ModelManager(ap)
    contexts = {workspace: ExecutionContext('instance', workspace, 1) for workspace in ('a', 'b')}
    # Only execution binding discovery is stubbed; cache indexing/removal/close is real.
    manager.resolve_execution_context = AsyncMock(side_effect=lambda context: contexts[context])
    service = ModelProviderService(ap)
    closed = []

    async def snapshot():
        async with engine.connect() as conn:
            return {
                table.__tablename__: [dict(row) for row in (await conn.execute(sa.select(table))).mappings()]
                for table in TABLES
            }

    async with engine.begin() as conn:
        for table in (User, Workspace, ModelProvider, CodexCredential, *MODEL_TYPES):
            await conn.run_sync(table.__table__.create)
        for workspace in contexts:
            await conn.execute(
                sa.insert(Workspace).values(
                    uuid=workspace,
                    instance_uuid='instance',
                    name=workspace,
                    slug=workspace,
                    source='cloud_projection',
                )
            )
        for provider, workspace in (('target', 'a'), ('neighbor', 'a'), ('foreign', 'b'), ('empty', 'a')):
            await conn.execute(
                sa.insert(ModelProvider).values(
                    uuid=provider,
                    workspace_uuid=workspace,
                    name=provider,
                    requester='openai-codex',
                    base_url='https://chatgpt.com/backend-api/codex',
                    api_keys=[],
                )
            )
            await conn.execute(
                sa.insert(CodexCredential).values(
                    provider_uuid=provider,
                    workspace_uuid=workspace,
                    payload={'synthetic': provider},
                )
            )

            async def close(provider=provider):
                # A separate connection must observe the durable deletion before close runs.
                state = await snapshot()
                assert all(row['uuid'] != provider for row in state['model_providers'])
                assert pm.current_session() is None
                closed.append(provider)

            runtime = SimpleNamespace(requester=SimpleNamespace(aclose=AsyncMock(side_effect=close)))
            manager._cache_set(manager.provider_dict, manager._cache_key(contexts[workspace], provider), runtime)
            if provider == 'empty':
                continue
            for model_type, cache in zip(
                MODEL_TYPES,
                (
                    manager.llm_model_dict,
                    manager.embedding_model_dict,
                    manager.rerank_model_dict,
                ),
            ):
                for index in range(2):
                    uuid = f'{provider}-{model_type.__tablename__}-{index}'
                    await conn.execute(
                        sa.insert(model_type).values(
                            uuid=uuid,
                            workspace_uuid=workspace,
                            provider_uuid=provider,
                            name=uuid,
                        )
                    )
                    manager._cache_set(cache, manager._cache_key(contexts[workspace], uuid), object())
    initial = await snapshot()
    initial_caches = [
        dict(cache)
        for cache in (
            manager.provider_dict,
            manager.llm_model_dict,
            manager.embedding_model_dict,
            manager.rerank_model_dict,
        )
    ]
    try:
        yield SimpleNamespace(
            ap=ap,
            pm=pm,
            engine=engine,
            service=service,
            manager=manager,
            snapshot=snapshot,
            initial=initial,
            initial_caches=initial_caches,
            closed=closed,
        )
    finally:
        await engine.dispose()


def assert_caches_unchanged(deletion):
    assert deletion.closed == []
    assert deletion.initial_caches == [
        dict(cache)
        for cache in (
            deletion.manager.provider_dict,
            deletion.manager.llm_model_dict,
            deletion.manager.embedding_model_dict,
            deletion.manager.rerank_model_dict,
        )
    ]


@pytest.mark.parametrize('mode', [PersistenceMode.OSS_COMPAT, PersistenceMode.CLOUD_RUNTIME])
async def test_cascade_deletes_all_model_types_and_credentials_after_commit(deletion, mode):
    deletion.pm.mode = mode
    await deletion.service.delete_provider('a', 'target', cascade=True)
    state = await deletion.snapshot()
    for table, rows in deletion.initial.items():
        identity = 'uuid' if table == 'model_providers' else 'provider_uuid'
        assert state[table] == [row for row in rows if row[identity] != 'target']
    assert deletion.closed == ['target']
    deletion.ap.logger.warning.assert_not_called()
    for cache in (
        deletion.manager.provider_dict,
        deletion.manager.llm_model_dict,
        deletion.manager.embedding_model_dict,
        deletion.manager.rerank_model_dict,
    ):
        assert all(not key[-1].startswith('target') for key in cache)
        assert any(key[1] == 'b' for key in cache)
        assert any(key[-1].startswith('neighbor') for key in cache)


@pytest.mark.parametrize('model_type', MODEL_TYPES)
@pytest.mark.parametrize('kwargs', [{}, {'cascade': False}])
async def test_default_guard_preserves_each_model_type(deletion, model_type, kwargs):
    async with deletion.engine.begin() as conn:
        for other in MODEL_TYPES:
            if other is not model_type:
                await conn.execute(sa.delete(other).where(other.provider_uuid == 'target'))
    before = await deletion.snapshot()
    with pytest.raises(ValueError, match='models still reference it'):
        await deletion.service.delete_provider('a', 'target', **kwargs)
    assert await deletion.snapshot() == before
    assert_caches_unchanged(deletion)


@pytest.mark.parametrize('kwargs', [{}, {'cascade': False}, {'cascade': True}])
async def test_empty_provider_deletes_credentials_with_or_without_cascade(deletion, kwargs):
    await deletion.service.delete_provider('a', 'empty', **kwargs)
    state = await deletion.snapshot()
    assert all(row['uuid'] != 'empty' for row in state['model_providers'])
    assert all(row['provider_uuid'] != 'empty' for row in state['codex_credentials'])
    assert deletion.closed == ['empty']


@pytest.mark.parametrize('provider', ['foreign', 'missing'])
@pytest.mark.parametrize('cascade', [False, True])
async def test_foreign_and_missing_provider_are_non_enumerating(deletion, provider, cascade):
    with pytest.raises(WorkspaceNotFoundError, match='Provider not found'):
        await deletion.service.delete_provider('a', provider, cascade=cascade)
    assert await deletion.snapshot() == deletion.initial
    assert_caches_unchanged(deletion)


@pytest.mark.parametrize('cascade', [False, True])
async def test_cloud_managed_provider_cannot_be_deleted(deletion, cascade):
    async with deletion.engine.begin() as conn:
        await conn.execute(
            sa.update(ModelProvider)
            .where(ModelProvider.uuid == 'target')
            .values(
                requester='space-chat-completions',
            )
        )
    before = await deletion.snapshot()
    deletion.pm.mode = PersistenceMode.CLOUD_RUNTIME
    with pytest.raises(ValueError, match='managed by Cloud'):
        await deletion.service.delete_provider('a', 'target', cascade=cascade)
    assert await deletion.snapshot() == before
    assert_caches_unchanged(deletion)


@pytest.mark.parametrize('failure_table', ['embedding_models', 'codex_credentials', 'model_providers'])
async def test_database_failure_rolls_back_all_rows_without_runtime_cleanup(deletion, failure_table):
    async with deletion.engine.begin() as conn:
        await conn.exec_driver_sql(
            f'CREATE TRIGGER fail_delete BEFORE DELETE ON {failure_table} '
            "BEGIN SELECT RAISE(ABORT, 'injected delete failure'); END"
        )
    with pytest.raises(sa.exc.IntegrityError, match='injected delete failure'):
        await deletion.service.delete_provider('a', 'target', cascade=True)
    assert await deletion.snapshot() == deletion.initial
    assert_caches_unchanged(deletion)


@pytest.mark.parametrize('rollback', [False, True])
async def test_nested_transaction_defers_cleanup_until_outer_commit(deletion, rollback):
    class Abort(Exception):
        pass

    try:
        async with deletion.pm.tenant_uow('a'):
            await deletion.service.delete_provider('a', 'target', cascade=True)
            assert_caches_unchanged(deletion)
            if rollback:
                raise Abort
    except Abort:
        pass
    tasks = tuple(deletion.service._deletion_tasks)
    await asyncio.gather(*tasks, return_exceptions=True)
    if rollback:
        assert await deletion.snapshot() == deletion.initial
        assert_caches_unchanged(deletion)
    else:
        assert deletion.closed == ['target']
        deletion.ap.logger.warning.assert_not_called()


async def test_cascade_ignores_foreign_workspace_references_even_without_foreign_keys(deletion):
    async with deletion.engine.connect() as conn:
        await conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
        for model_type in MODEL_TYPES:
            await conn.execute(
                sa.update(model_type)
                .where(model_type.workspace_uuid == 'b')
                .values(
                    provider_uuid='target',
                )
            )
        await conn.commit()
    await deletion.service.delete_provider('a', 'target', cascade=True)
    state = await deletion.snapshot()
    for model_type in MODEL_TYPES:
        assert len([row for row in state[model_type.__tablename__] if row['workspace_uuid'] == 'b']) == 2
    assert all(row['provider_uuid'] != 'target' for row in state['codex_credentials'])
    assert deletion.closed == ['target']


@pytest_asyncio.fixture
async def route_app(deletion):
    ap = deletion.ap
    ap.user_service = SimpleNamespace(
        get_authenticated_account=AsyncMock(
            return_value=SimpleNamespace(uuid='account', user='owner@example.invalid'),
        )
    )
    membership = SimpleNamespace(uuid='membership', role='owner', projection_revision=0)
    ap.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(
            return_value=SimpleNamespace(
                workspace=SimpleNamespace(uuid='a'),
                membership=membership,
                execution=SimpleNamespace(instance_uuid='instance', placement_generation=1),
            ),
        )
    )
    ap.provider_service = SimpleNamespace(delete_provider=AsyncMock())
    app = quart.Quart(__name__)
    await ModelProvidersRouterGroup(ap, app).initialize()
    return app.test_client(), ap.provider_service.delete_provider, membership


@pytest.mark.parametrize('query, expected', [('', None), ('?cascade=true', True), ('?cascade=false', False)])
async def test_route_passes_explicit_cascade_and_trusted_workspace(route_app, query, expected):
    client, delete, _ = route_app
    response = await client.delete(
        '/api/v1/provider/providers/target' + query,
        headers={
            'Authorization': 'Bearer token',
            'X-Workspace-Id': 'a',
        },
    )
    assert response.status_code == 200
    assert delete.await_count == 1
    assert delete.await_args.args[0].workspace_uuid == 'a'
    assert delete.await_args.args[1] == 'target'
    assert delete.await_args.kwargs == ({} if expected is None else {'cascade': expected})


@pytest.mark.parametrize(
    'query',
    [
        '?cascade=',
        '?cascade',
        '?cascade=TRUE',
        '?cascade=1',
        '?cascade=yes',
        '?cascade=null',
        '?cascade=%20true',
        '?cascade=true&cascade=false',
        '?cascade=true&cascade=true',
    ],
)
async def test_route_rejects_invalid_or_duplicate_cascade_before_deletion(route_app, query):
    client, delete, _ = route_app
    response = await client.delete(
        '/api/v1/provider/providers/target' + query,
        headers={
            'Authorization': 'Bearer token',
            'X-Workspace-Id': 'a',
        },
    )
    assert response.status_code == 400
    delete.assert_not_awaited()


@pytest.mark.parametrize('role', ['viewer', 'operator'])
async def test_cascade_requires_workspace_resource_manage_permission(route_app, role):
    client, delete, membership = route_app
    membership.role = role
    response = await client.delete(
        '/api/v1/provider/providers/target?cascade=true',
        headers={
            'Authorization': 'Bearer token',
            'X-Workspace-Id': 'a',
        },
    )
    assert response.status_code == 403
    delete.assert_not_awaited()


@pytest.mark.parametrize(
    'provider, query, status',
    [
        ('target', '', 400),
        ('target', '?cascade=false', 400),
        ('target', '?cascade=true', 200),
        ('foreign', '?cascade=true', 404),
        ('missing', '?cascade=true', 404),
    ],
)
async def test_route_to_real_sqlite_service(deletion, route_app, provider, query, status):
    client, _, _ = route_app
    deletion.ap.provider_service = deletion.service
    # The route forwards RequestContext, unlike the string-context service tests.
    deletion.manager.resolve_execution_context = AsyncMock(
        side_effect=lambda context: ExecutionContext(
            context.instance_uuid,
            context.workspace_uuid,
            context.placement_generation,
        )
    )
    response = await client.delete(
        '/api/v1/provider/providers/' + provider + query,
        headers={
            'Authorization': 'Bearer token',
            'X-Workspace-Id': 'a',
        },
    )
    assert response.status_code == status
    if status == 200:
        assert deletion.closed == ['target']
        for model_type in MODEL_TYPES:
            assert all(
                row['provider_uuid'] != 'target' for row in (await deletion.snapshot())[model_type.__tablename__]
            )
    else:
        assert await deletion.snapshot() == deletion.initial
        assert_caches_unchanged(deletion)
