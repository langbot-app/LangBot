from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart

from langbot.pkg.api.http.context import (
    ExecutionContext,
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.controller.groups.box import BoxRouterGroup
from langbot.pkg.api.http.controller.groups.monitoring import MonitoringRouterGroup
from langbot.pkg.api.http.controller.groups.pipelines.pipelines import PipelinesRouterGroup
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.api.http.service.pipeline_run import run_pipeline
from langbot.pkg.pipeline.pool import QueryPool
from langbot.pkg.pipeline.pipelinemgr import RuntimePipeline, StageInstContainer
from langbot.pkg.pipeline.entities import StageProcessResult, ResultType
from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter, WebSocketSession
from langbot.pkg.cloud.entitlements import EntitlementUnavailableError
from .test_monitoring_tenancy import service as service, WORKSPACE_A, WORKSPACE_B, _context, _record_message

pytestmark = pytest.mark.asyncio


def request_context(workspace=WORKSPACE_A, permissions=('resource.view', 'runtime.operate', 'audit.view')):
    return RequestContext(
        instance_uuid='instance',
        placement_generation=3,
        request_id='request',
        auth_type='api_key',
        principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=f'key-{workspace}'),
        workspace=WorkspaceContext(workspace, None, None, frozenset(permissions)),
    )


async def diagnostic_client(ap):
    async def authenticate(key):
        if key not in {'a', 'b', 'viewer', 'none'}:
            raise ValueError('Invalid API key')
        ctx = request_context(
            WORKSPACE_B if key == 'b' else WORKSPACE_A,
            ()
            if key == 'none'
            else ('resource.view',)
            if key == 'viewer'
            else ('resource.view', 'runtime.operate', 'resource.manage', 'audit.view'),
        )
        return SimpleNamespace(
            instance_uuid=ctx.instance_uuid,
            workspace_uuid=ctx.workspace_uuid,
            placement_generation=ctx.placement_generation,
            api_key_uuid=ctx.principal.api_key_uuid,
            permissions=ctx.workspace.permissions,
        )

    ap.apikey_service = SimpleNamespace(authenticate_api_key=authenticate)
    app = quart.Quart(__name__)
    for cls in (MonitoringRouterGroup, BoxRouterGroup, PipelinesRouterGroup):
        await cls(ap, app).initialize()
    return app.test_client()


async def test_http_api_key_diagnostics_are_scoped_bounded_and_permission_checked(service):  # noqa: F811
    ap = service.ap
    ap.logger = Mock()
    ap.monitoring_service = service
    ap.box_service = SimpleNamespace(
        get_status=AsyncMock(return_value={'enabled': False, 'available': False}),
        get_sessions=AsyncMock(return_value=[]),
        get_recent_errors=Mock(return_value=[]),
        managed_admission_required=False,
    )
    client = await diagnostic_client(ap)
    message_a = await _record_message(service, _context(WORKSPACE_A), 'only-a')
    await _record_message(service, _context(WORKSPACE_B), 'only-b')
    for key, expected, excluded in [('a', 'only-a', 'only-b'), ('b', 'only-b', 'only-a')]:
        response = await client.get(
            '/api/v1/monitoring/messages?limit=1', headers={'X-API-Key': key, 'X-Workspace-Id': WORKSPACE_B}
        )
        assert response.status_code == 200
        text = await response.get_data(as_text=True)
        assert expected in text and excluded not in text
    response = await client.get(f'/api/v1/monitoring/messages/{message_a}/details', headers={'X-API-Key': 'b'})
    assert response.status_code == 404
    assert (await client.get('/api/v1/monitoring/messages', headers={'X-API-Key': 'none'})).status_code == 403
    assert (await client.get('/api/v1/monitoring/messages')).status_code == 401
    for route in ('llm-calls', 'tool-calls', 'embedding-calls', 'sessions', 'errors'):
        assert (await client.get('/api/v1/monitoring/' + route, headers={'X-API-Key': 'a'})).status_code == 200
    for route in ('sessions', 'errors'):
        assert (await client.get('/api/v1/box/' + route, headers={'X-API-Key': 'viewer'})).status_code == 403
        response = await client.get('/api/v1/box/' + route, headers={'X-API-Key': 'a'})
        assert response.status_code == 200 and (await response.get_json())['data'] == []
    assert (await client.get('/api/v1/box/runtime-status', headers={'X-API-Key': 'a'})).status_code == 401
    response = await client.get('/api/v1/box/status', headers={'X-API-Key': 'viewer'})
    assert (await response.get_json())['data']['enabled'] is False
    ap.box_service.get_status.side_effect = EntitlementUnavailableError('Sandbox unavailable')
    response = await client.get('/api/v1/box/status', headers={'X-API-Key': 'a'})
    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'managed_sandbox_unavailable'


def runtime_app(monitoring_service):
    ap = monitoring_service.ap
    ap.logger = Mock()
    ap.monitoring_service = monitoring_service
    ap.query_pool = QueryPool()
    ap.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance'))
    )
    ap.plugin_connector = SimpleNamespace(
        emit_event=AsyncMock(
            side_effect=lambda event_obj, *_: SimpleNamespace(event=event_obj, is_prevented_default=lambda: False)
        )
    )
    ap.bot_service = SimpleNamespace(get_bot=AsyncMock(return_value={'name': 'CLI'}))
    ap.pipeline_service = SimpleNamespace(get_pipeline=AsyncMock(return_value={'uuid': 'p'}))
    adapters = {}

    async def proxy(context):
        if context.workspace_uuid not in adapters:
            logger = Mock(execution_context=ExecutionContext.from_request(context))
            adapters[context.workspace_uuid] = WebSocketAdapter.model_construct(ap=ap, logger=logger)
            adapters[context.workspace_uuid].websocket_person_session = WebSocketSession(id='person')
            adapters[context.workspace_uuid].websocket_group_session = WebSocketSession(id='group')
        return SimpleNamespace(adapter=adapters[context.workspace_uuid])

    ap.platform_mgr = SimpleNamespace(get_websocket_proxy_bot=proxy)
    return ap


async def process_next(ap, *, fail=False):
    while not ap.query_pool.queries:
        await asyncio.sleep(0)
    query = ap.query_pool.queries[0]
    async with ap.query_pool:
        ap.query_pool.mark_query_running_locked(query)

    class ReplyStage:
        async def process(self, query, _name):
            return StageProcessResult(
                result_type=ResultType.CONTINUE,
                new_query=query,
                user_notice='reply:' + str(query.message_chain),
                error_notice='model unavailable' if fail else '',
            )

    pipeline = RuntimePipeline(
        ap,
        SimpleNamespace(
            uuid='p',
            workspace_uuid=query.workspace_uuid,
            name='Test',
            extensions_preferences={},
            config={'output': {'misc': {'at-sender': False, 'quote-origin': False}}},
        ),
        [StageInstContainer('reply', ReplyStage())],
        ExecutionContext.from_request(request_context(query.workspace_uuid), pipeline_uuid='p'),
    )
    await pipeline.run(query)
    return query


async def test_run_route_executes_pipeline_and_isolates_sessions_and_workspaces(service):  # noqa: F811
    ap = runtime_app(service)
    client = await diagnostic_client(ap)
    assert (
        await client.post('/api/v1/pipelines/p/run', headers={'X-API-Key': 'viewer'}, json={'message': 'x'})
    ).status_code == 403
    sessions = set()
    for key, text in [('a', 'first'), ('a', 'second'), ('b', 'other-workspace')]:
        task = asyncio.create_task(process_next(ap))
        response = await asyncio.wait_for(
            client.post('/api/v1/pipelines/p/run', headers={'X-API-Key': key}, json={'message': text}), 3
        )
        if response.status_code != 200:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            pytest.fail(await response.get_data(as_text=True))
        query = await task
        assert response.status_code == 200
        data = (await response.get_json())['data']
        assert data['status'] == 'completed'
        assert data['reply'] == 'reply:' + text
        assert data['session_id'] not in sessions
        sessions.add(data['session_id'])
        assert query.workspace_uuid == (WORKSPACE_B if key == 'b' else WORKSPACE_A)
        assert data['message_id']
    a_records, _ = await service.get_messages(_context(WORKSPACE_A))
    assert 'other-workspace' not in str(a_records)


async def test_run_failure_timeout_and_missing_pipeline(service):  # noqa: F811
    ap = runtime_app(service)
    task = asyncio.create_task(process_next(ap, fail=True))
    failed = await run_pipeline(ap, request_context(), 'p', 'fail')
    await task
    assert failed['status'] == 'failed' and failed['message_id']
    errors, total = await service.get_errors(_context(WORKSPACE_A))
    assert total == 1 and errors[0]['error_message'] == 'model unavailable'
    unknown = await run_pipeline(ap, request_context(), 'p', 'slow', timeout=0.001)
    assert unknown['status'] == 'unknown' and len(ap.query_pool.queries) == 1
    await process_next(ap)
    assert not ap.query_pool.cached_queries
    ap.pipeline_service.get_pipeline.return_value = None
    from langbot.pkg.workspace.errors import WorkspaceNotFoundError

    with pytest.raises(WorkspaceNotFoundError):
        await run_pipeline(ap, request_context(), 'missing', 'x')
    assert not ap.query_pool.queries


async def test_extension_discovery_preserves_empty_bindings_and_redacts_plugins():
    ap = SimpleNamespace(
        plugin_connector=SimpleNamespace(
            is_enable_plugin=True,
            require_workspace_context=AsyncMock(),
            list_plugins=AsyncMock(return_value=[{'api_key': 'private'}]),
        ),
        mcp_service=SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[])),
        skill_service=SimpleNamespace(list_skills=AsyncMock(return_value=[])),
    )
    pipeline_service = PipelineService(ap)
    pipeline_service.get_pipeline = AsyncMock(
        return_value={'extensions_preferences': {'enable_all_plugins': False, 'plugins': []}}
    )
    data = await pipeline_service.get_pipeline_extensions(request_context(), 'p')
    assert data['bound_plugins'] == [] and data['enable_all_plugins'] is False
    assert data['available_plugins'] == [{'api_key': '***'}]
    ap.plugin_connector.require_workspace_context.assert_awaited_once_with(request_context())


@pytest.mark.compiled_cli
@pytest.mark.contract('cli_http')
async def test_compiled_cli_against_core_http(service, tmp_path):  # noqa: F811
    """Optional cross-repo check: real HTTP/SQLite/Pipeline, synthetic runtime providers."""
    import json
    import os
    import socket
    from pathlib import Path
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    import sqlalchemy
    from langbot.pkg.api.http.controller.groups.system import SystemRouterGroup
    from langbot.pkg.api.http.controller.groups.knowledge.engines import KnowledgeEnginesRouterGroup
    from langbot.pkg.api.http.controller.groups.knowledge.parsers import ParsersRouterGroup
    from langbot.pkg.api.http.service.knowledge import KnowledgeService
    from langbot.pkg.entity.persistence.pipeline import LegacyPipeline

    binary = os.environ.get('LANGBOT_CLI_BIN')
    if not binary:
        pytest.skip('Set LANGBOT_CLI_BIN to a compiled lbctl for the cross-repo HTTP check')
    assert Path(binary).is_file()
    ap = runtime_app(service)
    ap.pipeline_service = PipelineService(ap)
    ap.pipeline_mgr = SimpleNamespace(remove_pipeline=AsyncMock(), load_pipeline=AsyncMock())
    await ap.persistence_mgr.execute_async(
        sqlalchemy.insert(LegacyPipeline).values(
            uuid='p',
            workspace_uuid=WORKSPACE_A,
            name='CLI test',
            description='',
            for_version='1',
            stages=[],
            config={},
        )
    )
    ap.plugin_connector.is_enable_plugin = True
    ap.plugin_connector.require_workspace_context = AsyncMock()
    ap.plugin_connector.list_plugins = AsyncMock(return_value=[])
    ap.plugin_connector.list_knowledge_engines = AsyncMock(
        return_value=[{'plugin_id': 'author/engine', 'capabilities': ['doc_ingestion']}]
    )
    ap.plugin_connector.get_rag_creation_schema = AsyncMock(return_value={'type': 'object'})
    ap.plugin_connector.get_rag_retrieval_schema = AsyncMock(return_value={'type': 'object'})
    ap.plugin_connector.list_parsers = AsyncMock(return_value=[{'id': 'text', 'supported_mime_types': ['text/plain']}])
    ap.knowledge_service = KnowledgeService(ap)
    ap.mcp_service = SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[]))
    ap.skill_service = SimpleNamespace(list_skills=AsyncMock(return_value=[]))
    ap.box_service = SimpleNamespace(
        get_status=AsyncMock(return_value={'enabled': False, 'available': False}),
        get_sessions=AsyncMock(return_value=[]),
        get_recent_errors=Mock(return_value=[]),
        managed_admission_required=False,
    )
    client = await diagnostic_client(ap)
    original_authenticate = ap.apikey_service.authenticate_api_key

    async def smoke_authenticate(key):
        return await original_authenticate('a' if key == 'lbk_synthetic_smoke_key_7f36c0' else 'invalid')

    ap.apikey_service.authenticate_api_key = smoke_authenticate
    for cls in (SystemRouterGroup, KnowledgeEnginesRouterGroup, ParsersRouterGroup):
        await cls(ap, client.app).initialize()
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    config = Config()
    config.bind = [f'fd://{listener.detach()}']
    config.accesslog = None
    shutdown = asyncio.Event()
    server = asyncio.create_task(serve(client.app, config, shutdown_trigger=shutdown.wait))
    cli_config = tmp_path / 'cli.yaml'
    env = {k: v for k, v in os.environ.items() if not k.startswith('LANGBOT_')}
    env['SMOKE_KEY'] = 'lbk_synthetic_smoke_key_7f36c0'

    async def cli(*args, code=0):
        process = await asyncio.create_subprocess_exec(
            binary,
            '--config',
            str(cli_config),
            '-o',
            'json',
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(process.communicate(), 5)
        assert process.returncode == code, (out.decode(), err.decode())
        return json.loads(out)

    try:
        async with asyncio.timeout(3):
            while True:
                try:
                    _, writer = await asyncio.open_connection('127.0.0.1', port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.01)
        await cli(
            'context',
            'add',
            'smoke',
            '--endpoint',
            f'http://127.0.0.1:{port}',
            '--api-key-env',
            'SMOKE_KEY',
            '--expect-workspace',
            WORKSPACE_A,
        )
        await cli('context', 'use', 'smoke')
        for args in [
            ('knowledge-engine', 'list'),
            ('knowledge-engine', 'creation-schema', 'author/engine'),
            ('knowledge-engine', 'retrieval-schema', 'author/engine'),
            ('knowledge-parser', 'list', '--mime-type', 'text/plain'),
            ('sandbox', 'status'),
            ('sandbox', 'sessions'),
            ('sandbox', 'errors'),
        ]:
            assert (await cli(*args))['ok']
        await cli('knowledge-engine', 'creation-schema', 'missing/engine', code=5)
        body = {
            'bound_plugins': [],
            'bound_mcp_servers': [],
            'bound_skills': [],
            'bound_mcp_resources': [],
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'enable_all_skills': False,
            'mcp_resource_agent_read_enabled': False,
        }
        body_path = tmp_path / 'extensions.json'
        body_path.write_text(json.dumps(body))
        updated = await cli('pipeline', 'extensions', 'update', 'p', '--file', str(body_path))
        assert all(updated['data'][k] == v for k, v in body.items())
        task = asyncio.create_task(process_next(ap))
        result = await cli('pipeline', 'run', 'p', '--message', 'HTTP smoke')
        await task
        assert result['data']['status'] == 'completed' and result['data']['reply'] == 'reply:HTTP smoke'
        await cli('monitoring', 'message', result['data']['message_id'])
        await cli('monitoring', 'session', result['data']['session_id'])
        for kind in ('messages', 'llm-calls', 'tool-calls', 'embedding-calls', 'sessions', 'errors'):
            assert (await cli('monitoring', kind, '--limit', '1'))['ok']
    finally:
        shutdown.set()
        await server
