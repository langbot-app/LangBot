from __future__ import annotations

import sys
import types
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

core_app_module = types.ModuleType('langbot.pkg.core.app')
core_app_module.Application = object
sys.modules.setdefault('langbot.pkg.core.app', core_app_module)


pytestmark = pytest.mark.asyncio


async def _create_test_client(tool_mgr: SimpleNamespace, pipeline_service: SimpleNamespace):
    app = quart.Quart(__name__)
    user_service = SimpleNamespace(
        verify_jwt_token=AsyncMock(return_value='test@example.com'),
        get_user_by_email=AsyncMock(return_value=SimpleNamespace(user='test@example.com')),
    )
    ap = SimpleNamespace(
        tool_mgr=tool_mgr,
        pipeline_service=pipeline_service,
        user_service=user_service,
    )
    router_class = import_module('langbot.pkg.api.http.controller.groups.resources.tools').ToolsRouterGroup
    group = router_class(ap, app)
    await group.initialize()
    return app.test_client()


async def test_global_tool_selector_uses_unambiguous_host_catalog():
    tool_mgr = SimpleNamespace(
        get_resolved_tool_catalog=AsyncMock(return_value=[{'name': 'unique_tool', 'source': 'builtin'}])
    )
    pipeline_service = SimpleNamespace(get_pipeline=AsyncMock())
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        '/api/v1/tools',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data']['tools'] == [{'name': 'unique_tool', 'source': 'builtin'}]
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        None,
        None,
        include_skill_authoring=True,
    )
    pipeline_service.get_pipeline.assert_not_awaited()


async def test_pipeline_tool_selector_resolves_only_bound_sources():
    tool_mgr = SimpleNamespace(
        get_resolved_tool_catalog=AsyncMock(
            return_value=[
                {
                    'name': 'shared_tool',
                    'source': 'mcp',
                    'source_id': 'bound-mcp',
                }
            ]
        )
    )
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={
                'extensions_preferences': {
                    'enable_all_plugins': False,
                    'plugins': [{'author': 'allowed', 'name': 'plugin'}],
                    'enable_all_mcp_servers': False,
                    'mcp_servers': ['bound-mcp'],
                }
            }
        )
    )
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        '/api/v1/tools?pipeline_id=pipeline-1',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data']['tools'][0]['source_id'] == 'bound-mcp'
    pipeline_service.get_pipeline.assert_awaited_once_with('pipeline-1')
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        ['allowed/plugin'],
        ['bound-mcp'],
        include_skill_authoring=True,
    )


@pytest.mark.parametrize('invalid_value', [0, None, 'false'])
async def test_pipeline_tool_selector_malformed_enable_all_flags_fail_closed(invalid_value):
    tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=[]))
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={
                'extensions_preferences': {
                    'enable_all_plugins': invalid_value,
                    'plugins': [{'author': 'allowed', 'name': 'plugin'}],
                    'enable_all_mcp_servers': invalid_value,
                    'mcp_servers': ['bound-mcp'],
                }
            }
        )
    )
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        '/api/v1/tools?pipeline_id=pipeline-1',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        ['allowed/plugin'],
        ['bound-mcp'],
        include_skill_authoring=True,
    )


@pytest.mark.parametrize('invalid_preferences', [None, [], 'all', 0, False])
async def test_pipeline_tool_selector_malformed_extension_root_uses_empty_allowlists(
    invalid_preferences,
):
    tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=[]))
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={'extensions_preferences': invalid_preferences}
        )
    )
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        '/api/v1/tools?pipeline_id=pipeline-1',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        [],
        [],
        include_skill_authoring=True,
    )


async def test_pipeline_tool_selector_malformed_binding_lists_use_empty_allowlists():
    tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=[]))
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={
                'extensions_preferences': {
                    'enable_all_plugins': True,
                    'plugins': 'allowed/plugin',
                    'enable_all_mcp_servers': True,
                    'mcp_servers': 'bound-mcp',
                }
            }
        )
    )
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        '/api/v1/tools?pipeline_id=pipeline-1',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        [],
        [],
        include_skill_authoring=True,
    )


@pytest.mark.parametrize('pipeline_query_key', ['pipeline_uuid', 'pipeline_id'])
async def test_tool_detail_uses_pipeline_scoped_catalog_and_path_tool_name(pipeline_query_key):
    tool_mgr = SimpleNamespace(
        get_resolved_tool_catalog=AsyncMock(
            return_value=[
                {
                    'name': 'namespace/unique_tool',
                    'description': 'Unique tool',
                    'human_desc': 'A unique tool',
                    'parameters': {'type': 'object'},
                    'source': 'plugin',
                    'source_name': 'allowed/plugin',
                    'source_id': 'allowed/plugin',
                }
            ]
        )
    )
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={
                'extensions_preferences': {
                    'enable_all_plugins': False,
                    'plugins': [{'author': 'allowed', 'name': 'plugin'}],
                    'enable_all_mcp_servers': False,
                    'mcp_servers': ['bound-mcp'],
                }
            }
        )
    )
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        f'/api/v1/tools/namespace%2Funique_tool?{pipeline_query_key}=pipeline-1',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data']['tool'] == {
        'name': 'namespace/unique_tool',
        'description': 'Unique tool',
        'human_desc': 'A unique tool',
        'parameters': {'type': 'object'},
        'source': 'plugin',
        'source_name': 'allowed/plugin',
        'source_id': 'allowed/plugin',
    }
    pipeline_service.get_pipeline.assert_awaited_once_with('pipeline-1')
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        ['allowed/plugin'],
        ['bound-mcp'],
        include_skill_authoring=True,
    )


async def test_global_builtin_tool_detail_includes_nullable_source_id():
    tool_mgr = SimpleNamespace(
        get_resolved_tool_catalog=AsyncMock(
            return_value=[
                {
                    'name': 'exec',
                    'description': 'Execute a command',
                    'human_desc': 'Execute',
                    'parameters': {'type': 'object'},
                    'source': 'builtin',
                    'source_name': 'LangBot',
                }
            ]
        )
    )
    client = await _create_test_client(tool_mgr, SimpleNamespace(get_pipeline=AsyncMock()))

    response = await client.get(
        '/api/v1/tools/exec',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data']['tool']['source'] == 'builtin'
    assert payload['data']['tool']['source_id'] is None


async def test_tool_detail_hides_ambiguous_or_missing_name():
    tool_mgr = SimpleNamespace(
        get_resolved_tool_catalog=AsyncMock(return_value=[{'name': 'other_tool', 'source': 'builtin'}])
    )
    client = await _create_test_client(tool_mgr, SimpleNamespace(get_pipeline=AsyncMock()))

    response = await client.get(
        '/api/v1/tools/shared_tool',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 404
    tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
        None,
        None,
        include_skill_authoring=True,
    )


async def test_tool_detail_returns_pipeline_not_found_before_catalog_lookup():
    tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock())
    pipeline_service = SimpleNamespace(get_pipeline=AsyncMock(return_value=None))
    client = await _create_test_client(tool_mgr, pipeline_service)

    response = await client.get(
        '/api/v1/tools/unique_tool?pipeline_uuid=missing-pipeline',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 404
    assert await response.get_json() == {'code': -1, 'msg': 'pipeline not found'}
    pipeline_service.get_pipeline.assert_awaited_once_with('missing-pipeline')
    tool_mgr.get_resolved_tool_catalog.assert_not_awaited()
