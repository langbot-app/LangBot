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


async def _create_test_client(pipeline_service: SimpleNamespace, **extra_ap):
    app = quart.Quart(__name__)
    user_service = SimpleNamespace(
        verify_jwt_token=AsyncMock(return_value='test@example.com'),
        get_user_by_email=AsyncMock(return_value=SimpleNamespace(user='test@example.com')),
    )
    ap = SimpleNamespace(pipeline_service=pipeline_service, user_service=user_service, **extra_ap)
    router_class = import_module('langbot.pkg.api.http.controller.groups.pipelines.pipelines').PipelinesRouterGroup
    group = router_class(ap, app)
    await group.initialize()
    return app.test_client()


@pytest.mark.parametrize(
    ('method', 'path', 'service_method'),
    [
        ('post', '/api/v1/pipelines', 'create_pipeline'),
        ('put', '/api/v1/pipelines/pipeline-1', 'update_pipeline'),
    ],
)
async def test_pipeline_writes_return_bad_request_for_invalid_runner_security_field(
    method,
    path,
    service_method,
):
    message = "Pipeline runner_config['runner-1'] field 'enable-all-tools' must be a boolean"
    pipeline_service = SimpleNamespace(
        create_pipeline=AsyncMock(),
        update_pipeline=AsyncMock(),
        update_pipeline_extensions=AsyncMock(),
    )
    getattr(pipeline_service, service_method).side_effect = ValueError(message)
    client = await _create_test_client(pipeline_service)

    response = await getattr(client, method)(
        path,
        json={'config': {'ai': {'runner': {'id': 'runner-1'}}}},
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 400
    assert await response.get_json() == {'code': -1, 'msg': message}


@pytest.mark.parametrize('invalid_value', [0, None, 'false'])
async def test_pipeline_extensions_reject_non_boolean_resource_read(invalid_value):
    pipeline_service = SimpleNamespace(
        create_pipeline=AsyncMock(),
        update_pipeline=AsyncMock(),
        update_pipeline_extensions=AsyncMock(),
    )
    client = await _create_test_client(pipeline_service)

    response = await client.put(
        '/api/v1/pipelines/pipeline-1/extensions',
        json={'mcp_resource_agent_read_enabled': invalid_value},
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 400
    assert await response.get_json() == {
        'code': -1,
        'msg': "Pipeline extension field 'mcp_resource_agent_read_enabled' must be a boolean",
    }
    pipeline_service.update_pipeline_extensions.assert_not_awaited()


@pytest.mark.parametrize(
    'field',
    [
        'enable_all_plugins',
        'enable_all_mcp_servers',
        'enable_all_skills',
    ],
)
@pytest.mark.parametrize('invalid_value', [0, None, 'false'])
async def test_pipeline_extensions_reject_non_boolean_enable_all_flags(field, invalid_value):
    pipeline_service = SimpleNamespace(
        create_pipeline=AsyncMock(),
        update_pipeline=AsyncMock(),
        update_pipeline_extensions=AsyncMock(),
    )
    client = await _create_test_client(pipeline_service)

    response = await client.put(
        '/api/v1/pipelines/pipeline-1/extensions',
        json={field: invalid_value},
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 400
    assert await response.get_json() == {
        'code': -1,
        'msg': f"Pipeline extension field '{field}' must be a boolean",
    }
    pipeline_service.update_pipeline_extensions.assert_not_awaited()


@pytest.mark.parametrize(
    ('field', 'invalid_value'),
    [
        ('bound_plugins', 'author/plugin'),
        ('bound_mcp_servers', 'server-1'),
        ('bound_skills', 'skill-1'),
        ('bound_mcp_resources', {'uri': 'file:///README.md'}),
    ],
)
async def test_pipeline_extensions_return_bad_request_for_malformed_binding_lists(
    field,
    invalid_value,
):
    message = f"Pipeline extension field '{field}' must be a list"
    pipeline_service = SimpleNamespace(
        create_pipeline=AsyncMock(),
        update_pipeline=AsyncMock(),
        update_pipeline_extensions=AsyncMock(side_effect=ValueError(message)),
    )
    client = await _create_test_client(pipeline_service)

    response = await client.put(
        '/api/v1/pipelines/pipeline-1/extensions',
        json={field: invalid_value},
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 400
    assert await response.get_json() == {'code': -1, 'msg': message}


@pytest.mark.parametrize('invalid_value', [0, None, 'false'])
async def test_pipeline_extensions_get_normalizes_malformed_enable_all_flags(invalid_value):
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={
                'extensions_preferences': {
                    'enable_all_plugins': invalid_value,
                    'enable_all_mcp_servers': invalid_value,
                    'enable_all_skills': invalid_value,
                    'mcp_resource_agent_read_enabled': invalid_value,
                }
            }
        ),
    )
    client = await _create_test_client(
        pipeline_service,
        plugin_connector=SimpleNamespace(list_plugins=AsyncMock(return_value=[])),
        mcp_service=SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[])),
        skill_service=SimpleNamespace(list_skills=AsyncMock(return_value=[])),
        logger=SimpleNamespace(warning=AsyncMock()),
    )

    response = await client.get(
        '/api/v1/pipelines/pipeline-1/extensions',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data']['enable_all_plugins'] is False
    assert payload['data']['enable_all_mcp_servers'] is False
    assert payload['data']['enable_all_skills'] is False
    assert payload['data']['mcp_resource_agent_read_enabled'] is False


@pytest.mark.parametrize('invalid_preferences', [None, [], 'all', 0, False])
async def test_pipeline_extensions_get_malformed_root_is_fail_closed(invalid_preferences):
    pipeline_service = SimpleNamespace(
        get_pipeline=AsyncMock(
            return_value={'extensions_preferences': invalid_preferences}
        ),
    )
    client = await _create_test_client(
        pipeline_service,
        plugin_connector=SimpleNamespace(list_plugins=AsyncMock(return_value=[])),
        mcp_service=SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[])),
        skill_service=SimpleNamespace(list_skills=AsyncMock(return_value=[])),
        logger=SimpleNamespace(warning=AsyncMock()),
    )

    response = await client.get(
        '/api/v1/pipelines/pipeline-1/extensions',
        headers={'Authorization': 'Bearer test-token'},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload['data']['enable_all_plugins'] is False
    assert payload['data']['enable_all_mcp_servers'] is False
    assert payload['data']['enable_all_skills'] is False
    assert payload['data']['mcp_resource_agent_read_enabled'] is False
    assert payload['data']['bound_plugins'] == []
    assert payload['data']['bound_mcp_servers'] == []
    assert payload['data']['bound_skills'] == []
    assert payload['data']['bound_mcp_resources'] == []
