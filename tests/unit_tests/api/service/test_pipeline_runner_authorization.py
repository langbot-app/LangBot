"""Persisted Runner/allowlist consistency through the real Pipeline service."""

import copy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


pytestmark = pytest.mark.asyncio
RID = 'plugin:langbot-team/LocalAgent/default'
OTHER_RID = 'plugin:other/LocalAgent/default'
CONFIG = {'ai': {'runner': {'id': RID}, 'runner_config': {RID: {}}}}
ALLOWED = {'enable_all_plugins': False, 'plugins': [{'author': 'langbot-team', 'name': 'LocalAgent'}]}
DENIED = {'enable_all_plugins': False, 'plugins': []}


@pytest.fixture
async def env(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "runner-authorization.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sa.insert(Workspace),
            [
                dict(uuid=ws, instance_uuid='instance', name=ws, slug=ws, source='cloud_projection')
                for ws in ('workspace-test', 'b')
            ],
        )
        await connection.execute(
            sa.insert(LegacyPipeline),
            [
                dict(
                    uuid=pid,
                    workspace_uuid=ws,
                    name=pid,
                    description='',
                    for_version='4.11',
                    stages=[],
                    config=CONFIG,
                    extensions_preferences=ALLOWED,
                )
                for pid, ws in [('pipeline', 'workspace-test'), ('foreign', 'b')]
            ],
        )
    ap = NS(
        instance_config=NS(data={}),
        ver_mgr=NS(get_current_version=lambda: '4.11'),
        pipeline_mgr=NS(load_pipeline=AsyncMock(), remove_pipeline=AsyncMock()),
        sess_mgr=NS(session_list=[]),
        runner_registry=NS(list_runners=AsyncMock(return_value=[NS(id=RID, config_schema=[])])),
        plugin_connector=NS(is_enable_plugin=False, list_plugins=AsyncMock(return_value=[])),
        mcp_service=NS(get_mcp_servers=AsyncMock(return_value=[])),
        skill_service=NS(list_skills=AsyncMock(return_value=[])),
    )
    ap.persistence_mgr = PersistenceManager(ap)
    ap.persistence_mgr.db = NS(get_engine=lambda: engine)
    service = PipelineService(ap)
    try:
        yield service, ap
    finally:
        await engine.dispose()


@pytest.mark.parametrize('operation', ['config', 'preferences', 'combined', 'extensions', 'create', 'copy'])
async def test_rejected_changes_leave_database_and_runtime_unchanged(env, operation):
    service, ap = env
    if operation in ('config', 'copy'):
        # Seed an existing inconsistent configuration without using the service.
        await ap.persistence_mgr.execute_async(
            sa.update(LegacyPipeline).where(LegacyPipeline.uuid == 'pipeline').values(extensions_preferences=DENIED)
        )
    before = await service.get_pipelines('workspace-test', include_secret=True)
    with pytest.raises(ValueError, match='pipeline_runner_not_authorized'):
        if operation == 'config':
            await service.update_pipeline('workspace-test', 'pipeline', {'config': copy.deepcopy(CONFIG)})
        elif operation == 'preferences':
            await service.update_pipeline('workspace-test', 'pipeline', {'extensions_preferences': DENIED})
        elif operation == 'combined':
            await service.update_pipeline(
                'workspace-test', 'pipeline', {'config': CONFIG, 'extensions_preferences': DENIED}
            )
        elif operation == 'extensions':
            await service.update_pipeline_extensions('workspace-test', 'pipeline', [], enable_all_plugins=False)
        elif operation == 'create':
            await service.create_pipeline(
                'workspace-test', {'name': 'new', 'description': '', 'extensions_preferences': DENIED}
            )
        else:
            await service.copy_pipeline('workspace-test', 'pipeline')
    assert await service.get_pipelines('workspace-test', include_secret=True) == before
    ap.pipeline_mgr.load_pipeline.assert_not_awaited()
    ap.pipeline_mgr.remove_pipeline.assert_not_awaited()


@pytest.mark.parametrize('preferences', [ALLOWED, {'enable_all_plugins': True, 'plugins': []}, {}])
async def test_allowed_configurations_are_persisted(env, preferences):
    service, _ = env
    await service.update_pipeline(
        'workspace-test', 'pipeline', {'config': CONFIG, 'extensions_preferences': preferences}
    )
    saved = await service.get_pipeline('workspace-test', 'pipeline', include_secret=True)
    assert saved['config'] == CONFIG
    assert saved['extensions_preferences'] == preferences


async def test_allowlist_checks_author_as_well_as_plugin_name(env):
    service, _ = env
    config = {'ai': {'runner': {'id': OTHER_RID}, 'runner_config': {OTHER_RID: {}}}}
    with pytest.raises(ValueError, match='pipeline_runner_not_authorized'):
        await service.update_pipeline('workspace-test', 'pipeline', {'config': config})


async def test_combined_update_uses_new_config_and_new_allowlist(env):
    service, _ = env
    config = {'ai': {'runner': {'id': OTHER_RID}, 'runner_config': {OTHER_RID: {}}}}
    prefs = {'enable_all_plugins': False, 'plugins': [{'author': 'other', 'name': 'LocalAgent'}]}
    await service.update_pipeline('workspace-test', 'pipeline', {'config': config, 'extensions_preferences': prefs})
    saved = await service.get_pipeline('workspace-test', 'pipeline', include_secret=True)
    assert saved['config'] == config
    assert saved['extensions_preferences'] == prefs


async def test_extension_update_can_repair_an_existing_invalid_binding(env):
    service, ap = env
    await ap.persistence_mgr.execute_async(
        sa.update(LegacyPipeline).where(LegacyPipeline.uuid == 'pipeline').values(extensions_preferences=DENIED)
    )
    await service.update_pipeline_extensions('workspace-test', 'pipeline', ALLOWED['plugins'], enable_all_plugins=False)
    saved = await service.get_pipeline('workspace-test', 'pipeline')
    assert saved['extensions_preferences']['plugins'] == ALLOWED['plugins']
    assert saved['extensions_preferences']['enable_all_plugins'] is False


async def test_no_selected_runner_allows_an_empty_plugin_list(env):
    service, _ = env
    config = {'ai': {'runner': {'id': ''}, 'runner_config': {}}}
    await service.update_pipeline('workspace-test', 'pipeline', {'config': config, 'extensions_preferences': DENIED})
    assert (await service.get_pipeline('workspace-test', 'pipeline'))['config'] == config


@pytest.mark.parametrize('extensions_only', [False, True])
async def test_foreign_workspace_is_rejected_before_runner_validation(env, extensions_only):
    service, _ = env
    before = await service.get_pipeline('b', 'foreign', include_secret=True)
    with pytest.raises(WorkspaceNotFoundError):
        if extensions_only:
            await service.update_pipeline_extensions('workspace-test', 'foreign', [], enable_all_plugins=False)
        else:
            await service.update_pipeline('workspace-test', 'foreign', {'extensions_preferences': DENIED})
    assert await service.get_pipeline('b', 'foreign', include_secret=True) == before


@pytest.mark.parametrize('extensions_only', [False, True])
async def test_http_rejects_conflicting_save_without_persisting(env, extensions_only):
    from tests.unit_tests.api.test_pipelines_controller import _create_test_client

    service, _ = env
    client = await _create_test_client(service)
    before = await service.get_pipeline('workspace-test', 'pipeline', include_secret=True)
    path = '/api/v1/pipelines/pipeline'
    body = {'extensions_preferences': DENIED}
    if extensions_only:
        path += '/extensions'
        body = {'enable_all_plugins': False, 'bound_plugins': []}
    response = await client.put(path, json=body, headers={'Authorization': 'Bearer test-token'})
    assert response.status_code == 400
    assert await response.get_json() == {'code': -1, 'msg': 'pipeline_runner_not_authorized'}
    assert await service.get_pipeline('workspace-test', 'pipeline', include_secret=True) == before


async def test_runner_plugins_are_available_for_authorization_in_http_and_service(env):
    from tests.unit_tests.api.test_pipelines_controller import _create_test_client

    service, ap = env
    runner_plugin = {'manifest': {'manifest': {'metadata': ALLOWED['plugins'][0]}}, 'components': []}

    async def list_plugins(component_kinds):
        return [runner_plugin] if 'Runner' in component_kinds else []

    ap.plugin_connector = NS(is_enable_plugin=False, list_plugins=list_plugins)
    ap.mcp_service = NS(get_mcp_servers=AsyncMock(return_value=[]))
    ap.skill_service = NS(list_skills=AsyncMock(return_value=[]))
    client = await _create_test_client(
        service,
        plugin_connector=ap.plugin_connector,
        mcp_service=ap.mcp_service,
        skill_service=ap.skill_service,
    )
    response = await client.get(
        '/api/v1/pipelines/pipeline/extensions',
        headers={'Authorization': 'Bearer test-token'},
    )
    assert response.status_code == 200
    assert (await response.get_json())['data']['available_plugins'] == [runner_plugin]
    assert (await service.get_pipeline_extensions('workspace-test', 'pipeline'))['available_plugins'] == [runner_plugin]


@pytest.mark.parametrize('extensions_only', [False, True])
async def test_mcp_uses_same_save_validation(env, monkeypatch, extensions_only):
    from langbot.pkg.api.http.authz import permissions_for_role
    from langbot.pkg.api.http.context import RequestContext, PrincipalContext, PrincipalType, WorkspaceContext
    from langbot.pkg.api.mcp.server import LangBotMCPServer
    from mcp.server.fastmcp.exceptions import ToolError

    service, ap = env
    ap.pipeline_service = service
    context = RequestContext(
        'instance',
        1,
        'request',
        'api_key',
        PrincipalContext(PrincipalType.API_KEY, api_key_uuid='test-key'),
        WorkspaceContext('workspace-test', None, 'owner', permissions_for_role('owner')),
    )
    monkeypatch.setattr('langbot.pkg.api.mcp.server.get_request_context', lambda: context)
    server = LangBotMCPServer(ap)
    name = 'update_pipeline'
    arguments = {'pipeline_uuid': 'pipeline', 'pipeline_data': {'extensions_preferences': DENIED}}
    if extensions_only:
        name = 'update_pipeline_extensions'
        arguments = dict(
            pipeline_uuid='pipeline',
            bound_plugins=[],
            bound_mcp_servers=[],
            bound_skills=[],
            bound_mcp_resources=[],
            enable_all_plugins=False,
            enable_all_mcp_servers=True,
            enable_all_skills=True,
            mcp_resource_agent_read_enabled=True,
        )
    before = await service.get_pipeline('workspace-test', 'pipeline', include_secret=True)
    with pytest.raises(ToolError, match='pipeline_runner_not_authorized'):
        await server.mcp.call_tool(name, arguments)
    assert await service.get_pipeline('workspace-test', 'pipeline', include_secret=True) == before
