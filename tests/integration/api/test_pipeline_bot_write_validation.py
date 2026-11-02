import copy
import asyncio
import json
import logging
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart
import sqlalchemy as sa
import aiohttp
from hypercorn.asyncio import serve
from hypercorn.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.application import ApplicationAPI, ApplicationAPIException
from langbot.pkg.api.http.controller.groups.pipelines.pipelines import PipelinesRouterGroup
from langbot.pkg.api.http.controller.groups.platform.bots import BotsRouterGroup
from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.entity.persistence.bot import Bot
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.pipeline.cntfilter.cntfilter import ContentFilterStage
from langbot.pkg.pipeline.pipelinemgr import PipelineManager
from langbot.pkg.utils.paths import get_resource_path
from langbot.pkg.workspace.service import WorkspaceService
from tests.integration.api.test_application_foundation import context


@pytest.fixture
async def write_foundation(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "writes.db"}')
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync,
                    tables=[
                        model.__table__
                        for model in (Workspace, WorkspaceExecutionState, WorkspaceMetadata, LegacyPipeline, Bot)
                    ],
                )
            )
            await connection.execute(
                sa.insert(Workspace).values(
                    uuid='workspace-a',
                    instance_uuid='foundation-instance',
                    name='Test',
                    slug='test',
                    source='cloud_projection',
                )
            )
            await connection.execute(
                sa.insert(WorkspaceExecutionState).values(
                    workspace_uuid='workspace-a',
                    instance_uuid='foundation-instance',
                    active_generation=1,
                    source='cloud',
                )
            )
        ap = SimpleNamespace(instance_config=SimpleNamespace(data={}), logger=logging.getLogger('write-validation'))
        ap.persistence_mgr = PersistenceManager(ap)
        ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
        ap.workspace_service = WorkspaceService(ap, instance_uuid='foundation-instance')
        yield ApplicationAPI(ap), ap, engine
    finally:
        await engine.dispose()


@pytest.fixture
async def writes(write_foundation):
    api, ap, engine = write_foundation
    ap.pipeline_service = PipelineService(ap)
    ap.bot_service = BotService(ap)
    ap.pipeline_mgr = PipelineManager(ap)
    ap.pipeline_mgr.stage_dict = {'ContentFilterStage': ContentFilterStage}
    ap.sess_mgr = SimpleNamespace(session_list=[])
    with open(get_resource_path('templates/default-pipeline-config.json')) as stream:
        config = json.load(stream)
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(LegacyPipeline).values(
                uuid='pipeline-a',
                workspace_uuid='workspace-a',
                name='Original',
                description='',
                for_version='test',
                stages=['ContentFilterStage'],
                config=config,
                extensions_preferences={},
                is_default=True,
            )
        )
    async with ap.persistence_mgr.tenant_scope('workspace-a'):
        pipeline = await ap.pipeline_service.get_pipeline(context(), 'pipeline-a', include_secret=True)
        await ap.pipeline_mgr.load_pipeline(context(), pipeline)
    ap.user_service = SimpleNamespace(
        get_authenticated_account=AsyncMock(return_value=SimpleNamespace(uuid='account-test', user='test@example.com'))
    )
    ap.apikey_service = SimpleNamespace(authenticate_api_key=AsyncMock(return_value=None))
    ap.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(
            return_value=SimpleNamespace(
                workspace=SimpleNamespace(uuid='workspace-a'),
                membership=SimpleNamespace(uuid='membership-test', role='owner', projection_revision=1),
                execution=SimpleNamespace(instance_uuid='foundation-instance', placement_generation=1),
            )
        )
    )
    app = quart.Quart(__name__)
    await PipelinesRouterGroup(ap, app).initialize()
    await BotsRouterGroup(ap, app).initialize()
    return api, ap, engine, app.test_client(), config


async def stored_pipeline(engine):
    async with engine.connect() as connection:
        return dict((await connection.execute(sa.select(LegacyPipeline))).mappings().one())


@pytest.mark.asyncio
@pytest.mark.parametrize('transport', ['http', 'application', 'service'])
@pytest.mark.parametrize('invalid', ['partial', 'runtime', 'null'])
async def test_invalid_pipeline_preserves_database_and_runtime(writes, transport, invalid):
    api, ap, engine, client, config = writes
    original = await stored_pipeline(engine)
    runtime = ap.pipeline_mgr.pipelines[0]
    if invalid == 'partial':
        config = {'ai': config['ai']}
    elif invalid == 'runtime':
        config['safety'] = {}
    else:
        config = None
    payload = {'name': 'Must not persist', 'config': config}
    if transport == 'http':
        response = await client.put(
            '/api/v1/pipelines/pipeline-a', json=payload, headers={'Authorization': 'Bearer test-token'}
        )
        assert response.status_code == 400, await response.get_json()
        print('pipeline.update', invalid, response.status_code, await response.get_json())
    elif transport == 'application':
        with pytest.raises(ApplicationAPIException) as failure:
            await api.execute('pipeline.update', context(), {'pipeline_uuid': 'pipeline-a', 'pipeline_data': payload})
        assert failure.value.error.status_code == 400
    else:
        async with ap.persistence_mgr.tenant_scope('workspace-a'):
            with pytest.raises(ValueError):
                await ap.pipeline_service.update_pipeline(context(), 'pipeline-a', payload)
    assert await stored_pipeline(engine) == original
    assert ap.pipeline_mgr.pipelines == [runtime]


@pytest.mark.asyncio
async def test_valid_pipeline_replaces_runtime_after_write(writes):
    _, ap, engine, client, config = writes
    previous = ap.pipeline_mgr.pipelines[0]
    response = await client.put(
        '/api/v1/pipelines/pipeline-a',
        json={'name': 'Updated', 'config': config},
        headers={'Authorization': 'Bearer test-token'},
    )
    assert response.status_code == 200, await response.get_json()
    assert (await stored_pipeline(engine))['name'] == 'Updated'
    assert ap.pipeline_mgr.pipelines[0] is not previous
    assert ap.pipeline_mgr.pipelines[0].pipeline_entity.name == 'Updated'


@pytest.mark.asyncio
async def test_failed_pipeline_write_does_not_publish_candidate(writes, monkeypatch):
    _, ap, engine, _, config = writes
    original = await stored_pipeline(engine)
    runtime = ap.pipeline_mgr.pipelines[0]
    execute = ap.persistence_mgr.execute_async

    async def fail_update(statement, *args, **kwargs):
        if isinstance(statement, sa.sql.dml.Update):
            raise RuntimeError('Database unavailable')
        return await execute(statement, *args, **kwargs)

    monkeypatch.setattr(ap.persistence_mgr, 'execute_async', fail_update)
    async with ap.persistence_mgr.tenant_scope('workspace-a'):
        with pytest.raises(RuntimeError, match='Database unavailable'):
            await ap.pipeline_service.update_pipeline(context(), 'pipeline-a', {'config': config, 'name': 'Unsaved'})
    assert await stored_pipeline(engine) == original
    assert ap.pipeline_mgr.pipelines == [runtime]


@pytest.mark.asyncio
@pytest.mark.parametrize('transport', ['http', 'application', 'service'])
@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('adapter_config', 'missing'),
        ('adapter_config', None),
        ('adapter_config', []),
        ('adapter', 'missing'),
        ('name', 'missing'),
        ('adapter', ''),
    ],
)
async def test_invalid_bot_has_no_database_side_effects(writes, transport, field, value):
    api, ap, engine, client, _ = writes
    pipeline = await stored_pipeline(engine)
    payload = {'name': 'Bot', 'adapter': 'aiocqhttp', 'adapter_config': {}}
    if value == 'missing':
        payload.pop(field)
    else:
        payload[field] = value
    original = copy.deepcopy(payload)
    if transport == 'http':
        response = await client.post(
            '/api/v1/platform/bots', json=payload, headers={'Authorization': 'Bearer test-token'}
        )
        assert response.status_code == 400, await response.get_json()
        assert field in (await response.get_json())['msg']
        print('bot.create', field, response.status_code, await response.get_json())
    elif transport == 'application':
        with pytest.raises(ApplicationAPIException) as failure:
            await api.execute('bot.create', context(), {'bot_data': payload})
        assert failure.value.error.status_code == 400
        assert field in failure.value.error.message
    else:
        async with ap.persistence_mgr.tenant_scope('workspace-a'):
            with pytest.raises(ValueError, match=field):
                await ap.bot_service.create_bot(context(), payload)
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(sa.func.count()).select_from(Bot))).scalar_one() == 0
    assert await stored_pipeline(engine) == pipeline
    assert payload == original


@pytest.mark.asyncio
async def test_bot_create_schema_lists_required_fields(writes):
    api, _, _, _, _ = writes
    operation = next(item for item in api.operation_catalog() if item['id'] == 'bot.create')
    schema = operation['input_schema']['properties']['bot_data']
    assert schema['required'] == ['name', 'adapter', 'adapter_config']
    assert schema['properties']['adapter_config']['type'] == 'object'


@pytest.mark.asyncio
async def test_valid_bot_binds_existing_pipeline(writes):
    _, _, engine, client, _ = writes
    response = await client.post(
        '/api/v1/platform/bots',
        json={
            'name': 'Bound bot',
            'adapter': 'aiocqhttp',
            'adapter_config': {},
            'enable': False,
        },
        headers={'Authorization': 'Bearer test-token'},
    )
    assert response.status_code == 200, await response.get_json()
    async with engine.connect() as connection:
        bot = (await connection.execute(sa.select(Bot))).mappings().one()
    assert bot['adapter_config'] == {}
    assert all(binding['target_uuid'] == 'pipeline-a' for binding in bot['event_bindings'])
    print('bot.create valid', response.status_code, await response.get_json(), 'bindings:', bot['event_bindings'])


@pytest.mark.asyncio
async def test_live_http_rejects_invalid_writes_without_dirty_rows(writes):
    _, ap, engine, client, _ = writes
    original = await stored_pipeline(engine)
    runtime = ap.pipeline_mgr.pipelines[0]
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    port = listener.getsockname()[1]
    config = Config()
    config.bind = [f'fd://{listener.detach()}']
    shutdown = asyncio.Event()
    server = asyncio.create_task(serve(client.app, config, shutdown_trigger=shutdown.wait))
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            for method, path, payload in (
                ('PUT', '/api/v1/pipelines/pipeline-a', {'name': 'Unsaved', 'config': {'ai': {}}}),
                ('POST', '/api/v1/platform/bots', {'name': 'Invalid bot', 'adapter': 'aiocqhttp'}),
            ):
                async with session.request(
                    method,
                    f'http://127.0.0.1:{port}{path}',
                    json=payload,
                    headers={'Authorization': 'Bearer test-token'},
                ) as response:
                    body = await response.json()
                    print(
                        json.dumps(
                            {
                                'method': method,
                                'path': path,
                                'request': payload,
                                'status': response.status,
                                'response': body,
                            }
                        )
                    )
                    assert response.status == 400
        assert await stored_pipeline(engine) == original
        async with engine.connect() as connection:
            assert (await connection.execute(sa.select(sa.func.count()).select_from(Bot))).scalar_one() == 0
        assert ap.pipeline_mgr.pipelines == [runtime]
        print('Independent SQLite readback: pipeline unchanged; bots=0; original runtime retained')
    finally:
        shutdown.set()
        await server
