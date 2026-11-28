from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
import sqlalchemy as sa
from quart import Quart
from sqlalchemy.ext.asyncio import create_async_engine
import yaml

from langbot.pkg.api.application import ApplicationAPI
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.http.controller.groups.pipelines.pipelines import PipelinesRouterGroup
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.api.http.service.mcp import MCPService
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.api.http.service.provider import ModelProviderService
from langbot.pkg.api.http.service.skill import SkillService
from langbot.pkg.api.mcp.context import get_request_context
from langbot.pkg.api.mcp.mount import MCPMount
from langbot.pkg.core.app import Application
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.apikey import ApiKey
from langbot.pkg.entity.persistence.mcp import MCPServer
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.model import ModelProvider
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.pipeline.pipelinemgr import PipelineManager
from langbot.pkg.plugin.connector import PluginRuntimeConnector
from langbot.pkg.skill.repository import SkillRepository
from langbot.pkg.workspace.service import WorkspaceService
from langbot.pkg.utils.paths import get_resource_path
from tests.integration.api.test_application_foundation import context


@pytest.mark.asyncio
async def test_mcp_session_tools_use_task_owned_scopes_and_real_services(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "mcp.db"}')
    application = Application()
    application.logger = logging.getLogger('mcp-task-scope')
    application.instance_config = SimpleNamespace(
        data={'plugin': {'enable': False}, 'skills': {'root': str(tmp_path / 'skills')}}
    )
    application.persistence_mgr = PersistenceManager(application, mode=PersistenceMode.CLOUD_RUNTIME)
    application.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
    application.workspace_service = WorkspaceService(application, instance_uuid='foundation-instance')
    application.apikey_service = ApiKeyService(application)
    application.pipeline_service = PipelineService(application)
    application.provider_service = ModelProviderService(application)
    application.pipeline_mgr = PipelineManager(application)
    for section in ('ai', 'speech', 'output'):
        with open(get_resource_path(f'templates/metadata/pipeline/{section}.yaml')) as metadata_file:
            setattr(application, f'pipeline_config_meta_{section}', yaml.safe_load(metadata_file))
    application.plugin_connector = PluginRuntimeConnector(application, None)
    application.mcp_service = MCPService(application)
    application.skill_service = SkillService(application)
    application.skill_repository = SkillRepository(application)
    application.application_api = ApplicationAPI(application)
    manager = application.persistence_mgr
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all,
                tables=[
                    model.__table__
                    for model in (
                        Workspace,
                        WorkspaceExecutionState,
                        ApiKey,
                        LegacyPipeline,
                        ModelProvider,
                        WorkspaceMetadata,
                        MCPServer,
                        PluginSetting,
                    )
                ],
            )
            await connection.execute(
                sa.insert(Workspace).values(
                    uuid='workspace-a', instance_uuid='foundation-instance', name='MCP', slug='mcp'
                )
            )
            await connection.execute(
                sa.insert(WorkspaceExecutionState).values(
                    workspace_uuid='workspace-a', instance_uuid='foundation-instance', active_generation=1
                )
            )
            await connection.execute(
                sa.insert(LegacyPipeline).values(
                    uuid='pipeline-a',
                    workspace_uuid='workspace-a',
                    name='MCP pipeline',
                    description='preserved',
                    for_version='test',
                    stages=[],
                    config={},
                    extensions_preferences={},
                )
            )
            await connection.execute(
                sa.insert(ModelProvider).values(
                    uuid='provider-a',
                    workspace_uuid='workspace-a',
                    name='MCP provider',
                    requester='openai',
                    base_url='https://example.test/v1',
                    api_keys=['synthetic-provider-secret'],
                )
            )
        async with manager.tenant_scope('workspace-a'):
            owner = await application.apikey_service.create_api_key(context(), 'owner')
            limited = await application.apikey_service.create_api_key(
                context(), 'limited', scopes=[Permission.RESOURCE_VIEW, Permission.RESOURCE_MANAGE]
            )
            viewer = await application.apikey_service.create_api_key(
                context(), 'viewer', scopes=[Permission.RESOURCE_VIEW]
            )

        quart_app = Quart(__name__)
        await PipelinesRouterGroup(application, quart_app).initialize()
        mount = MCPMount(application)
        dispatcher_task = None
        tool_tasks = []

        @mount.server.tool(description='Verify scope ownership and cleanup.')
        async def scope_probe(fail: bool = False) -> str:
            tool_tasks.append(asyncio.current_task())
            assert asyncio.current_task() is not dispatcher_task
            assert manager.current_scope() is not None
            assert manager.current_session() is None
            await manager.execute_async(sa.select(LegacyPipeline.uuid))
            assert manager.current_session() is None
            if fail:
                raise ValueError('probe failure')
            return get_request_context().workspace_uuid

        async def dispatch(scope, receive, send):
            nonlocal dispatcher_task
            dispatcher_task = asyncio.current_task()
            await mount.wrap(quart_app.asgi_app)(scope, receive, send)
            assert manager.current_scope() is None
            assert manager.current_session() is None
            with pytest.raises(RuntimeError, match='context is unavailable'):
                get_request_context()

        evidence = []
        extension_arguments = {
            'pipeline_uuid': 'pipeline-a',
            'bound_plugins': [],
            'bound_mcp_servers': [],
            'bound_skills': [],
            'bound_mcp_resources': [],
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'enable_all_skills': False,
            'mcp_resource_agent_read_enabled': False,
        }
        async with mount.server.session_manager.run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=dispatch), base_url='http://127.0.0.1:5300'
            ) as client:

                async def rpc(key, role, method, params):
                    request = {'jsonrpc': '2.0', 'id': len(evidence) + 1, 'method': method, 'params': params}
                    response = await client.post(
                        '/mcp',
                        json=request,
                        headers={
                            'X-API-Key': key['key'],
                            'Accept': 'application/json, text/event-stream',
                        },
                    )
                    assert response.status_code == 200, response.text
                    body = response.json()
                    evidence.append({'role': role, 'request': request, 'response': body})
                    assert 'Scoped persistence boundaries' not in response.text
                    assert 'synthetic-provider-secret' not in response.text
                    return body['result']

                async def call(key, role, name, arguments=None):
                    return await rpc(key, role, 'tools/call', {'name': name, 'arguments': arguments or {}})

                for role, key in [('owner', owner), ('limited', limited)]:
                    await rpc(
                        key,
                        role,
                        'initialize',
                        {
                            'protocolVersion': '2024-11-05',
                            'capabilities': {},
                            'clientInfo': {'name': 'scope-regression', 'version': '1'},
                        },
                    )
                    assert (await rpc(key, role, 'tools/list', {}))['tools']
                    for name in ('list_pipelines', 'list_model_providers', 'get_pipeline_extensions'):
                        arguments = {'pipeline_uuid': 'pipeline-a'} if name == 'get_pipeline_extensions' else {}
                        result = await call(key, role, name, arguments)
                        assert not result.get('isError'), result
                        payload = json.loads(result['content'][0]['text'])
                        if name == 'list_pipelines':
                            assert payload[0]['uuid'] == 'pipeline-a'
                        elif name == 'list_model_providers':
                            assert payload[0]['api_keys'] == ['***']
                    granted_operations = ['pipeline.list'] if role == 'owner' else ['pipeline.get', 'pipeline.list']
                    result = await call(
                        key,
                        role,
                        'update_pipeline_extensions',
                        {
                            **extension_arguments,
                            'workspace_operations': granted_operations,
                        },
                    )
                    assert not result.get('isError'), result
                    response = await client.get('/api/v1/pipelines/pipeline-a', headers={'X-API-Key': key['key']})
                    assert response.status_code == 200, response.text
                    readback = response.json()
                    evidence.append({'role': role, 'http_readback': readback})
                    assert (
                        readback['data']['pipeline']['extensions_preferences']['workspace_operations']
                        == granted_operations
                    )
                    result = await call(key, role, 'scope_probe')
                    assert not result.get('isError'), result
                    result = await call(key, role, 'scope_probe', {'fail': True})
                    assert result['isError']

                # Pipeline workspace operations only select among operations an
                # account already granted to the runner plugin installation, so a
                # manager may store a selection outside its own permissions.
                result = await call(
                    limited,
                    'limited',
                    'update_pipeline_extensions',
                    {
                        **extension_arguments,
                        'workspace_operations': ['model.llm.create'],
                    },
                )
                assert not result.get('isError'), result
                response = await client.get('/api/v1/pipelines/pipeline-a', headers={'X-API-Key': limited['key']})
                assert response.status_code == 200, response.text
                assert response.json()['data']['pipeline']['extensions_preferences']['workspace_operations'] == [
                    'model.llm.create'
                ]
                result = await call(
                    limited,
                    'limited',
                    'update_pipeline_extensions',
                    {
                        **extension_arguments,
                        'workspace_operations': ['pipeline.get', 'pipeline.list'],
                    },
                )
                assert not result.get('isError'), result
                denied = await call(
                    viewer,
                    'viewer',
                    'update_pipeline_extensions',
                    {
                        **extension_arguments,
                        'workspace_operations': [],
                    },
                )
                assert denied['isError']
                assert 'resource.manage' in json.dumps(denied)
                response = await client.get('/api/v1/pipelines/pipeline-a', headers={'X-API-Key': owner['key']})
                assert response.status_code == 200, response.text
                readback = response.json()
                evidence.append({'http_readback': readback})
                assert readback['data']['pipeline']['extensions_preferences']['workspace_operations'] == [
                    'pipeline.get',
                    'pipeline.list',
                ]
                assert readback['data']['pipeline']['description'] == 'preserved'

        assert tool_tasks
        assert manager.current_scope() is None
        async with engine.connect() as connection:
            preferences = await connection.scalar(sa.select(LegacyPipeline.extensions_preferences))
            assert preferences['workspace_operations'] == ['pipeline.get', 'pipeline.list']
        print('MCP_SQLITE_EVIDENCE=' + json.dumps(evidence, ensure_ascii=False))
    finally:
        await engine.dispose()
