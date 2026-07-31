"""Security regression tests for plugin configuration HTTP responses."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
import quart


pytestmark = pytest.mark.integration
WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'
RAW_CONFIG = {
    'apiKey': 'api-secret',
    'nested': {
        'headers': {'Authorization': 'Bearer nested-secret', 'Accept': 'application/json'},
        'refresh_token': 'refresh-secret',
        'public_key': 'public-material',
        'tokenizer': 'not-a-secret',
    },
    'credentials': {'username': 'service-user', 'password': 'service-password'},
    'secret_list': ['first-secret', {'value': 'second-secret'}],
    'empty_secret': '',
    'enabled': True,
}


def _access(account_uuid: str):
    roles = {
        'viewer-account': 'viewer',
        'operator-account': 'operator',
        'manager-account': 'developer',
    }
    return SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(
            uuid=f'membership-{account_uuid}',
            role=roles[account_uuid],
            projection_revision=1,
        ),
        execution=SimpleNamespace(instance_uuid='instance-test', placement_generation=1),
    )


@pytest.fixture(scope='module')
def plugin_module():
    """Import the plugin router without following the core HTTP cycle."""

    from tests.utils.import_isolation import MockLifecycleControlScope, isolated_sys_modules

    class FakeMinimalApplication:
        pass

    mock_app = Mock(Application=FakeMinimalApplication)
    mock_entities = Mock(LifecycleControlScope=MockLifecycleControlScope)
    clear = [
        'langbot.pkg.core.taskmgr',
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.plugins',
        'langbot.pkg.api.http.controller.main',
    ]
    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.plugins as plugins

        yield plugins


@pytest.fixture
async def plugin_security_api(plugin_module):
    viewer = SimpleNamespace(uuid='viewer-account', user='viewer@example.com')
    operator = SimpleNamespace(uuid='operator-account', user='operator@example.com')
    manager = SimpleNamespace(uuid='manager-account', user='manager@example.com')
    accounts = {
        'viewer-token': viewer,
        'operator-token': operator,
        'manager-token': manager,
    }

    application = Mock()
    application.deployment = SimpleNamespace(multi_workspace_enabled=False)
    application.user_service.get_authenticated_account = AsyncMock(side_effect=lambda token: accounts[token])
    application.workspace_collaboration_service.resolve_account_workspace = AsyncMock(
        side_effect=lambda account_uuid, _workspace_uuid: _access(account_uuid)
    )
    application.apikey_service.verify_api_key = AsyncMock(return_value=False)
    application.instance_config.data = {
        'plugin': {'display_plugin_debug_url': 'http://localhost:5401'},
        'system': {'limitation': {}},
    }

    raw_plugin = {
        'author': 'example',
        'name': 'secure-plugin',
        'plugin_config': RAW_CONFIG,
        'debug': {'plugin_debug_key': 'list-debug-secret'},
    }
    application.plugin_connector.require_workspace_context = AsyncMock()
    application.plugin_connector.list_plugins = AsyncMock(return_value=[raw_plugin])
    application.plugin_connector.get_plugin_info = AsyncMock(return_value=raw_plugin)
    application.plugin_connector.get_debug_info = AsyncMock(return_value={'plugin_debug_key': 'runtime-debug-secret'})
    application.plugin_connector.get_plugin_logs = AsyncMock(return_value=['private runtime line'])
    application.plugin_connector.set_plugin_config = AsyncMock()

    persistence_result = Mock()
    persistence_result.scalar_one_or_none.return_value = RAW_CONFIG
    application.persistence_mgr.execute_async = AsyncMock(return_value=persistence_result)
    application.persistence_mgr.tenant_uow = None

    quart_app = quart.Quart(__name__)
    router = plugin_module.PluginsRouterGroup(application, quart_app)
    await router.initialize()
    return application, quart_app.test_client(), raw_plugin


def _headers(token: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {token}',
        'X-Workspace-Id': WORKSPACE_UUID,
    }


def test_recursive_redaction_preserves_structure_without_mutating_input(plugin_module):
    redacted = plugin_module.redact_plugin_secrets(RAW_CONFIG)

    assert redacted['apiKey'] == '***'
    assert redacted['nested']['headers'] == {
        'Authorization': '***',
        'Accept': 'application/json',
    }
    assert redacted['nested']['refresh_token'] == '***'
    assert redacted['nested']['public_key'] == 'public-material'
    assert redacted['nested']['tokenizer'] == 'not-a-secret'
    assert redacted['credentials'] == {'username': '***', 'password': '***'}
    assert redacted['secret_list'] == ['***', {'value': '***'}]
    assert redacted['empty_secret'] == ''
    assert redacted['enabled'] is True
    assert RAW_CONFIG['apiKey'] == 'api-secret'
    assert RAW_CONFIG['nested']['headers']['Authorization'] == 'Bearer nested-secret'
    with pytest.raises(ValueError, match='no existing value'):
        plugin_module.restore_plugin_secret_placeholders({'api_key': '***'}, {})


@pytest.mark.asyncio
async def test_viewer_plugin_reads_are_recursively_redacted(plugin_security_api):
    application, client, raw_plugin = plugin_security_api

    list_response = await client.get('/api/v1/plugins', headers=_headers('viewer-token'))
    detail_response = await client.get(
        '/api/v1/plugins/example/secure-plugin',
        headers=_headers('viewer-token'),
    )
    config_response = await client.get(
        '/api/v1/plugins/example/secure-plugin/config',
        headers=_headers('viewer-token'),
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert config_response.status_code == 200
    listed_plugin = (await list_response.get_json())['data']['plugins'][0]
    detailed_plugin = (await detail_response.get_json())['data']['plugin']
    config = (await config_response.get_json())['data']['config']
    for plugin in (listed_plugin, detailed_plugin):
        assert plugin['plugin_config']['apiKey'] == '***'
        assert plugin['debug']['plugin_debug_key'] == '***'
    assert config['apiKey'] == '***'
    assert config['nested']['headers']['Authorization'] == '***'
    assert raw_plugin['plugin_config']['apiKey'] == 'api-secret'
    application.plugin_connector.require_workspace_context.assert_awaited()


@pytest.mark.asyncio
async def test_manager_read_is_redacted_but_write_preserves_or_replaces_secrets(
    plugin_security_api,
    plugin_module,
):
    application, client, _ = plugin_security_api

    read_response = await client.get(
        '/api/v1/plugins/example/secure-plugin/config',
        headers=_headers('manager-token'),
    )
    masked_update = plugin_module.redact_plugin_secrets(RAW_CONFIG)
    masked_update['enabled'] = False
    preserved_write = await client.put(
        '/api/v1/plugins/example/secure-plugin/config',
        headers=_headers('manager-token'),
        json=masked_update,
    )
    replacement = copy.deepcopy(RAW_CONFIG)
    replacement['apiKey'] = 'replacement-secret'
    replaced_write = await client.put(
        '/api/v1/plugins/example/secure-plugin/config',
        headers=_headers('manager-token'),
        json=replacement,
    )

    preserved = copy.deepcopy(RAW_CONFIG)
    preserved['enabled'] = False

    assert read_response.status_code == 200
    assert (await read_response.get_json())['data']['config']['apiKey'] == '***'
    assert preserved_write.status_code == 200
    assert replaced_write.status_code == 200
    assert application.plugin_connector.set_plugin_config.await_args_list == [
        call('example', 'secure-plugin', preserved),
        call('example', 'secure-plugin', replacement),
    ]


@pytest.mark.asyncio
async def test_debug_key_requires_resource_manage_permission(plugin_security_api):
    application, client, _ = plugin_security_api

    viewer_denied = await client.get('/api/v1/plugins/debug-info', headers=_headers('viewer-token'))
    operator_denied = await client.get('/api/v1/plugins/debug-info', headers=_headers('operator-token'))
    application.plugin_connector.get_debug_info.assert_not_awaited()
    allowed = await client.get('/api/v1/plugins/debug-info', headers=_headers('manager-token'))

    assert viewer_denied.status_code == 403
    assert operator_denied.status_code == 403
    assert allowed.status_code == 200
    assert (await allowed.get_json())['data'] == {
        'debug_url': 'http://localhost:5401',
        'plugin_debug_key': 'runtime-debug-secret',
    }
    application.plugin_connector.get_debug_info.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_viewer_cannot_read_plugin_runtime_logs(plugin_security_api):
    application, client, _ = plugin_security_api

    response = await client.get(
        '/api/v1/plugins/example/secure-plugin/logs',
        headers=_headers('viewer-token'),
    )

    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'permission_denied'
    application.plugin_connector.get_plugin_logs.assert_not_awaited()


@pytest.mark.asyncio
async def test_github_install_rejects_internal_asset_url_before_task_creation(
    plugin_security_api,
):
    application, client, _ = plugin_security_api

    response = await client.post(
        '/api/v1/plugins/install/github',
        headers=_headers('manager-token'),
        json={
            'asset_url': 'http://169.254.169.254/latest/meta-data',
            'owner': 'langbot-app',
            'repo': 'demo-plugin',
            'release_tag': 'v1.0.0',
        },
    )

    assert response.status_code == 400
    assert 'HTTPS GitHub release asset URL' in (await response.get_json())['msg']
    application.task_mgr.create_user_task.assert_not_called()
