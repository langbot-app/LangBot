from types import SimpleNamespace
from typing import get_args
from unittest.mock import AsyncMock
from dataclasses import replace

import pytest
from langbot_plugin.api.entities.permissions import Capability
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from langbot.pkg.api.application.contracts import ApplicationAPIException, Input, Operation
from langbot.pkg.api.application.execution import EXECUTION_OPERATIONS
from langbot.pkg.api.application.plugin_capabilities import (
    ACTION_CAPABILITIES,
    APPLICATION_ACTIONS,
    BINARY_STORAGE_ACTIONS,
    CAPABILITY_ACTIONS,
    CAPABILITY_PERMISSIONS,
    CONTEXT_ACTIONS,
    LEGACY_CAPABILITIES,
)
from langbot.pkg.api.application.plugin_permissions import (
    change_permissions,
    describe_permissions,
    effective_grants,
    expand_declaration,
    read_declaration,
)
from langbot.pkg.api.application.tool_grants import validate_grant_change
from langbot.pkg.api.authz import Permission, permissions_for_role
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.api.application.plugin_operations import install_marketplace_task
from langbot.pkg.core.taskmgr import TaskContext


def context(role='developer', principal=PrincipalType.ACCOUNT):
    return RequestContext(
        'instance',
        1,
        'request',
        'test',
        PrincipalContext(principal, account_uuid='member'),
        WorkspaceContext('workspace', None, role, permissions_for_role(role)),
    )


@pytest.fixture
def app():
    operations = {
        name: Operation(name, permission, AsyncMock(), Input, dict)
        for name, permission in [
            ('stats.basic', Permission.RESOURCE_VIEW),
            ('bot.list', Permission.RESOURCE_VIEW),
            ('bot.get', Permission.RESOURCE_VIEW),
        ]
    }
    return SimpleNamespace(
        application_api=SimpleNamespace(_operations=operations),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=SimpleNamespace(rowcount=1))),
        plugin_connector=SimpleNamespace(activate_permission_installation=AsyncMock()),
    )


def installation(declaration=None, grants=None, snapshot=None, enabled=True):
    return SimpleNamespace(
        installation_uuid='install',
        runtime_revision=1,
        permission_declaration=declaration,
        permission_grants=grants,
        permission_snapshot=snapshot,
        enabled=enabled,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('auto_confirm', [False, True])
async def test_marketplace_install_confirmation_is_explicit(app, auto_confirm):
    declaration = {'workspace_operations': ['stats.basic'], 'capabilities': ['models.invoke']}
    setting = installation(declaration, {}, enabled=False)
    app.plugin_connector.install_plugin = AsyncMock()
    app.plugin_connector._setting_for_plugin = AsyncMock(return_value=(None, setting))
    await install_marketplace_task(
        app,
        context(),
        {
            'plugin_author': 'test',
            'plugin_name': 'Runner',
            'auto_confirm_permissions': auto_confirm,
        },
        TaskContext.new(),
    )
    assert setting.enabled is auto_confirm
    assert describe_permissions(app, context(), setting)['pending_confirmation'] is not auto_confirm
    assert setting.permission_grants == (declaration if auto_confirm else {})
    assert 'auto_confirm_permissions' not in app.plugin_connector.install_plugin.await_args.args[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('principal', [PrincipalType.API_KEY, PrincipalType.PLUGIN])
async def test_marketplace_install_cannot_auto_confirm_nonmember(app, principal):
    setting = installation({'capabilities': ['models.invoke']}, {}, enabled=False)
    app.plugin_connector.install_plugin = AsyncMock()
    app.plugin_connector._setting_for_plugin = AsyncMock(return_value=(None, setting))
    task = TaskContext.new()
    with pytest.raises(ApplicationAPIException) as error:
        await install_marketplace_task(
            app,
            context(principal=principal),
            {
                'plugin_author': 'test',
                'plugin_name': 'Runner',
                'auto_confirm_permissions': True,
            },
            task,
        )
    assert error.value.error.code == 'permission_denied'
    assert task.metadata['permission_confirmation_error']['code'] == 'permission_denied'
    assert not setting.enabled and setting.permission_grants == {} and setting.permission_snapshot is None
    app.plugin_connector.activate_permission_installation.assert_not_awaited()


@pytest.mark.asyncio
async def test_marketplace_auto_confirmation_respects_member_ceiling(app):
    setting = installation({'capabilities': ['models.invoke']}, {}, enabled=False)
    app.plugin_connector.install_plugin = AsyncMock()
    app.plugin_connector._setting_for_plugin = AsyncMock(return_value=(None, setting))
    ctx = context()
    ctx = replace(ctx, workspace=replace(ctx.workspace, permissions=frozenset({Permission.RESOURCE_MANAGE})))
    task = TaskContext.new()
    with pytest.raises(ApplicationAPIException) as error:
        await install_marketplace_task(
            app,
            ctx,
            {
                'plugin_author': 'test',
                'plugin_name': 'Runner',
                'auto_confirm_permissions': True,
            },
            task,
        )
    assert error.value.error.details['denied_capabilities'] == ['models.invoke']
    assert task.metadata['permission_confirmation_error']['details']['denied_capabilities'] == ['models.invoke']
    assert not setting.enabled and setting.permission_grants == {} and setting.permission_snapshot is None
    app.plugin_connector.activate_permission_installation.assert_not_awaited()


def test_capability_and_action_catalogs_are_complete():
    assert set(get_args(Capability)) == set(CAPABILITY_PERMISSIONS) == set(CAPABILITY_ACTIONS) == LEGACY_CAPABILITIES
    actions = [action.value for group in CAPABILITY_ACTIONS.values() for action in group]
    assert len(actions) == len(set(actions))
    assert not (set(actions) & CONTEXT_ACTIONS)
    assert set(actions) | CONTEXT_ACTIONS | APPLICATION_ACTIONS == {
        action.value for action in PluginToRuntimeAction if action is not PluginToRuntimeAction.REGISTER_PLUGIN
    } | ({operation.action for operation in EXECUTION_OPERATIONS} - BINARY_STORAGE_ACTIONS)
    assert ACTION_CAPABILITIES[PluginToRuntimeAction.CALL_TOOL.value] == 'plugin_tools'


def test_missing_and_empty_declarations_are_distinct(app):
    assert read_declaration({'spec': {}}) is None
    strict = read_declaration({'spec': {'permissions': {}}})
    assert effective_grants(app, installation(strict)) == {'workspace_operations': [], 'capabilities': []}
    assert effective_grants(app, installation()) == {
        'workspace_operations': [],
        'capabilities': sorted(LEGACY_CAPABILITIES),
    }
    assert effective_grants(app, installation(grants={}, enabled=False)) == {
        'workspace_operations': [],
        'capabilities': [],
    }


def test_wildcard_is_a_confirmation_time_snapshot(app):
    declaration = {'workspace_operations': ['bot.*'], 'capabilities': []}
    snapshot = expand_declaration(app, declaration)
    setting = installation(declaration, snapshot, snapshot)
    app.application_api._operations['bot.delete'] = Operation(
        'bot.delete', Permission.RESOURCE_MANAGE, AsyncMock(), Input, dict
    )
    assert 'bot.delete' not in effective_grants(app, setting)['workspace_operations']
    assert describe_permissions(app, context(), setting)['pending_confirmation']


@pytest.mark.parametrize(
    'principal',
    [
        PrincipalType.API_KEY,
        PrincipalType.PLUGIN,
        PrincipalType.PROCESSOR,
        PrincipalType.SYSTEM,
        PrincipalType.PUBLIC_BOT,
    ],
)
def test_nonhuman_principals_cannot_add_grants(app, principal):
    with pytest.raises(ApplicationAPIException) as error:
        validate_grant_change(
            app, context(principal=principal), [], ['stats.basic'], principal_type=PrincipalType.PLUGIN
        )
    assert error.value.error.code == 'permission_denied'
    assert validate_grant_change(app, context(principal=principal), ['stats.basic'], []) == []


def test_capability_ceiling_checks_every_permission(app):
    with pytest.raises(ApplicationAPIException) as error:
        validate_grant_change(app, context('operator'), [], [], new_capabilities=['bot.platform_api'])
    assert error.value.error.details['denied_capabilities'] == ['bot.platform_api']
    validate_grant_change(app, context(), [], [], new_capabilities=list(LEGACY_CAPABILITIES))


@pytest.mark.asyncio
async def test_confirmation_revocation_and_upgrade(app):
    declaration = {'workspace_operations': ['stats.basic'], 'capabilities': ['models.invoke']}
    setting = installation(declaration, {}, enabled=False)
    result = await change_permissions(
        app, context(), setting, workspace_operations=['stats.basic'], capabilities=[], confirm=True
    )
    assert result['enabled'] and not result['pending_confirmation']
    assert effective_grants(app, setting)['workspace_operations'] == ['stats.basic']
    await change_permissions(
        app, context(principal=PrincipalType.API_KEY), setting, workspace_operations=[], capabilities=[], confirm=False
    )
    assert effective_grants(app, setting)['workspace_operations'] == []
    assert not describe_permissions(app, context(), setting)['pending_confirmation']
    setting.permission_declaration['workspace_operations'].append('bot.list')
    assert describe_permissions(app, context(), setting)['pending_confirmation']
    assert 'bot.list' not in effective_grants(app, setting)['workspace_operations']


@pytest.mark.asyncio
async def test_compatibility_requires_all_capabilities_then_allows_revocation(app):
    setting = installation(grants={}, enabled=False)
    with pytest.raises(ApplicationAPIException):
        await change_permissions(
            app, context(), setting, workspace_operations=[], capabilities=['models.invoke'], confirm=True
        )
    await change_permissions(
        app, context(), setting, workspace_operations=[], capabilities=sorted(LEGACY_CAPABILITIES), confirm=True
    )
    await change_permissions(
        app, context(), setting, workspace_operations=[], capabilities=['models.invoke'], confirm=False
    )
    assert effective_grants(app, setting)['capabilities'] == ['models.invoke']


@pytest.mark.asyncio
async def test_api_key_cannot_confirm_even_an_empty_declaration(app):
    setting = installation({'workspace_operations': [], 'capabilities': []}, {}, enabled=False)
    assert describe_permissions(app, context(principal=PrincipalType.API_KEY), setting)['can_confirm'] is False
    assert describe_permissions(app, context(), setting)['can_confirm'] is True
    with pytest.raises(ApplicationAPIException) as error:
        await change_permissions(
            app,
            context(principal=PrincipalType.API_KEY),
            setting,
            workspace_operations=[],
            capabilities=[],
            confirm=True,
        )
    assert error.value.error.code == 'permission_denied'


@pytest.mark.asyncio
async def test_protocol_capabilities_and_cross_workspace_bot_are_enforced(app, monkeypatch):
    from langbot.pkg.api.application import plugin_permissions

    binding = SimpleNamespace(workspace_uuid='workspace', installation_uuid='install')
    setting = installation({'workspace_operations': [], 'capabilities': ['bot.read']}, {'capabilities': ['bot.read']})
    monkeypatch.setattr(plugin_permissions, 'load_installation', AsyncMock(return_value=setting))
    await plugin_permissions.authorize_action(app, binding, PluginToRuntimeAction.GET_BOTS.value, {})
    with pytest.raises(ApplicationAPIException) as error:
        await plugin_permissions.authorize_action(app, binding, PluginToRuntimeAction.INVOKE_LLM.value, {})
    assert error.value.error.details['denied_capabilities'] == ['models.invoke']
    app.persistence_mgr.execute_async.return_value = SimpleNamespace(first=lambda: None)
    with pytest.raises(ApplicationAPIException) as error:
        await plugin_permissions.authorize_action(
            app, binding, PluginToRuntimeAction.GET_BOT_INFO.value, {'bot_uuid': 'foreign'}
        )
    assert error.value.error.code == 'permission_denied'
    setting.enabled = False
    with pytest.raises(ApplicationAPIException):
        await plugin_permissions.authorize_action(
            app, binding, PluginToRuntimeAction.EVENT_GET.value, {'run_id': 'run'}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('granted', [True, False])
@pytest.mark.parametrize('action', ['send_message', 'delete_message', 'call_platform_api'])
async def test_standard_send_uses_message_capability_without_generic_platform_access(app, monkeypatch, granted, action):
    from langbot.pkg.api.application import plugin_permissions

    capabilities = ['bot.message.send'] if granted else []
    declaration = {'workspace_operations': [], 'capabilities': capabilities}
    monkeypatch.setattr(
        plugin_permissions, 'load_installation', AsyncMock(return_value=installation(declaration, declaration))
    )
    app.persistence_mgr.execute_async.return_value = SimpleNamespace(first=lambda: ('bot',))
    binding = SimpleNamespace(workspace_uuid='workspace', installation_uuid='install')
    data = {'run_id': 'run', 'bot_uuid': 'bot', 'action': action}
    if action == 'send_message' and granted:
        await plugin_permissions.authorize_action(app, binding, PluginToRuntimeAction.CALL_PLATFORM_API.value, data)
    else:
        with pytest.raises(ApplicationAPIException) as error:
            await plugin_permissions.authorize_action(app, binding, PluginToRuntimeAction.CALL_PLATFORM_API.value, data)
        expected = 'bot.message.send' if action == 'send_message' else 'bot.platform_api'
        assert error.value.error.details['denied_capabilities'] == [expected]


@pytest.mark.asyncio
async def test_platform_tool_fallback_does_not_bypass_installation_grants(app, monkeypatch):
    from langbot.pkg.api.application import plugin_permissions
    from langbot.pkg.agent.runner.platform_tools import PLATFORM_TOOLS_BY_NAME

    binding = SimpleNamespace(workspace_uuid='workspace', installation_uuid='install')
    setting = installation({'workspace_operations': [], 'capabilities': []}, {})
    monkeypatch.setattr(plugin_permissions, 'load_installation', AsyncMock(return_value=setting))
    app.tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=[]))
    app.plugin_connector._runtime_handler = lambda: SimpleNamespace(_execution_context=lambda value: value)
    tool = next(item for item in PLATFORM_TOOLS_BY_NAME.values() if item.scope == 'platform')
    with pytest.raises(ApplicationAPIException) as error:
        await plugin_permissions.authorize_action(
            app, binding, PluginToRuntimeAction.CALL_TOOL.value, {'run_id': 'run', 'tool_name': tool.name}
        )
    assert error.value.error.code == 'permission_denied'
    with pytest.raises(ApplicationAPIException) as error:
        await plugin_permissions.authorize_action(
            app, binding, PluginToRuntimeAction.CALL_TOOL.value, {'run_id': 'run', 'tool_name': 'unknown'}
        )
    assert error.value.error.code == 'not_found'


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['native', 'builtin'])
async def test_native_sandbox_tools_require_the_sandbox_capability(app, monkeypatch, source):
    from langbot.pkg.api.application import plugin_permissions

    binding = SimpleNamespace(workspace_uuid='workspace', installation_uuid='install')
    catalog = [{'name': 'exec', 'source': source, 'source_id': None}]
    app.tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=catalog))
    app.plugin_connector._runtime_handler = lambda: SimpleNamespace(_execution_context=lambda value: value)
    data = {'run_id': 'run', 'tool_name': 'exec'}

    denied = installation({'workspace_operations': [], 'capabilities': ['sandbox']}, {'capabilities': []})
    monkeypatch.setattr(plugin_permissions, 'load_installation', AsyncMock(return_value=denied))
    with pytest.raises(ApplicationAPIException) as error:
        await plugin_permissions.authorize_action(app, binding, PluginToRuntimeAction.CALL_TOOL.value, dict(data))
    assert error.value.error.details['denied_capabilities'] == ['sandbox']

    granted = installation({'workspace_operations': [], 'capabilities': ['sandbox']}, {'capabilities': ['sandbox']})
    monkeypatch.setattr(plugin_permissions, 'load_installation', AsyncMock(return_value=granted))
    await plugin_permissions.authorize_action(app, binding, PluginToRuntimeAction.CALL_TOOL.value, dict(data))


def test_preferences_do_not_grant_or_check_member_ceiling(app):
    from langbot.pkg.api.application.tool_grants import validate_operation_preferences

    assert validate_operation_preferences(app, context('viewer', PrincipalType.API_KEY), [], ['stats.basic']) == [
        'stats.basic'
    ]
    with pytest.raises(ApplicationAPIException):
        validate_operation_preferences(app, context(), [], ['bot.*'])
    app.persistence_mgr.execute_async.assert_not_awaited()


def test_described_operations_carry_domain_metadata(app):
    setting = installation({'workspace_operations': ['stats.basic'], 'capabilities': ['models.invoke']}, {})
    described = describe_permissions(app, context(), setting)
    operation = next(item for item in described['permissions'] if item['id'] == 'stats.basic')
    capability = next(item for item in described['permissions'] if item['id'] == 'models.invoke')
    assert operation['domain'] == 'stats'
    assert 'domain' not in capability
    assert [domain['domain'] for domain in described['domains']] == ['stats']
    assert described['domains'][0]['label']


@pytest.mark.asyncio
@pytest.mark.parametrize('live', [True, False])
async def test_websocket_proxy_bot_is_authorized_by_live_runtime_not_bots_table(app, monkeypatch, live):
    from langbot.pkg.api.application import plugin_permissions
    from unittest.mock import Mock

    declaration = {'workspace_operations': [], 'capabilities': ['bot.read', 'bot.message.send']}
    monkeypatch.setattr(
        plugin_permissions, 'load_installation', AsyncMock(return_value=installation(declaration, declaration))
    )
    app.persistence_mgr.execute_async = AsyncMock(side_effect=AssertionError('proxy bot has no bots row'))
    app.platform_mgr = SimpleNamespace(has_websocket_proxy_bot=Mock(return_value=live))
    binding = SimpleNamespace(workspace_uuid='workspace', installation_uuid='install')
    for action, data in [
        (PluginToRuntimeAction.GET_BOT_INFO.value, {'bot_uuid': 'websocket-proxy-bot'}),
        (PluginToRuntimeAction.SEND_MESSAGE.value, {'bot_uuid': 'websocket-proxy-bot'}),
        (
            PluginToRuntimeAction.CALL_PLATFORM_API.value,
            {'bot_uuid': 'websocket-proxy-bot', 'action': 'send_message'},
        ),
    ]:
        if live:
            await plugin_permissions.authorize_action(app, binding, action, data)
        else:
            with pytest.raises(ApplicationAPIException) as error:
                await plugin_permissions.authorize_action(app, binding, action, data)
            assert error.value.error.code == 'permission_denied'
    app.platform_mgr.has_websocket_proxy_bot.assert_called_with('workspace')
    app.persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_proxy_bot_still_requires_the_send_capability(app, monkeypatch):
    from langbot.pkg.api.application import plugin_permissions

    declaration = {'workspace_operations': [], 'capabilities': []}
    monkeypatch.setattr(
        plugin_permissions, 'load_installation', AsyncMock(return_value=installation(declaration, declaration))
    )
    app.platform_mgr = SimpleNamespace(has_websocket_proxy_bot=lambda workspace_uuid: True)
    binding = SimpleNamespace(workspace_uuid='workspace', installation_uuid='install')
    with pytest.raises(ApplicationAPIException) as error:
        await plugin_permissions.authorize_action(
            app, binding, PluginToRuntimeAction.SEND_MESSAGE.value, {'bot_uuid': 'websocket-proxy-bot'}
        )
    assert error.value.error.details['denied_capabilities'] == ['bot.message.send']
