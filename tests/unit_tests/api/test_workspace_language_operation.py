"""Plugins and Agents read the Workspace message language through workspace.language.get."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.application.granted_operations import call, list_granted
from langbot.pkg.api.application.plugin_permissions import expand_declaration
from langbot.pkg.api.application.tool_grants import get_workspace_operations_catalog
from langbot.pkg.api.authz import Permission, permissions_for_role
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.i18n import SUPPORTED_LANGUAGES

OPERATION = 'workspace.language.get'


def member_context():
    return RequestContext(
        'instance-a',
        1,
        'request',
        'test',
        PrincipalContext(PrincipalType.ACCOUNT, account_uuid='member'),
        WorkspaceContext('workspace-a', None, 'owner', permissions_for_role('owner')),
    )


def agent_context(principal, allowed):
    # Mirrors installation_context / build_processor_request_context: permissions
    # are derived only from the granted operations.
    permissions = frozenset({Permission.WORKSPACE_VIEW.value}) if OPERATION in allowed else frozenset()
    return RequestContext(
        'instance-a',
        1,
        'request',
        'plugin' if principal == PrincipalType.PLUGIN else 'processor',
        PrincipalContext(principal, installation_uuid='installation', run_id='run'),
        WorkspaceContext('workspace-a', None, None, permissions),
        allowed_operation_ids=frozenset(allowed),
    )


def app(stored_language):
    result = Mock()
    result.scalar_one_or_none = Mock(return_value=stored_language)

    @asynccontextmanager
    async def tenant_uow(workspace_uuid):
        assert workspace_uuid == 'workspace-a'
        yield SimpleNamespace(execute=AsyncMock(return_value=result))

    @asynccontextmanager
    async def tenant_scope(workspace_uuid):
        yield

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_uow=tenant_uow, tenant_scope=tenant_scope),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance-a'))
        ),
        workspace_settings_service=SimpleNamespace(effective_level=AsyncMock(return_value=0), record=AsyncMock()),
        logger=Mock(),
    )
    ap.application_api = ApplicationAPI(ap)
    return ap


def test_language_get_is_grantable_but_update_is_not():
    ap = SimpleNamespace(application_api=ApplicationAPI(None))
    assert expand_declaration(ap, {'workspace_operations': [OPERATION]})['workspace_operations'] == [OPERATION]
    for rejected in (['workspace.language.update'], ['workspace.language.*'], ['workspace.*']):
        with pytest.raises(ApplicationAPIException):
            expand_declaration(ap, {'workspace_operations': rejected})

    catalog = {
        item['id']: item for item in get_workspace_operations_catalog(ap, member_context())['workspace_operations']
    }
    assert catalog[OPERATION]['risk'] == 'read'
    assert catalog[OPERATION]['grantable']
    assert catalog[OPERATION]['permission'] == Permission.WORKSPACE_VIEW.value
    assert 'workspace.language.update' not in catalog


@pytest.mark.asyncio
@pytest.mark.parametrize('principal', [PrincipalType.PLUGIN, PrincipalType.PROCESSOR])
async def test_granted_plugins_and_agents_read_the_workspace_language(principal):
    ap = app('zh_Hans')
    result = await ap.application_api.execute(OPERATION, agent_context(principal, {OPERATION}), {})
    assert result == {'language': 'zh_Hans', 'supported_languages': list(SUPPORTED_LANGUAGES)}


@pytest.mark.asyncio
async def test_unset_workspace_language_defaults_to_english():
    ap = app(None)
    result = await ap.application_api.execute(OPERATION, agent_context(PrincipalType.PLUGIN, {OPERATION}), {})
    assert result['language'] == 'en_US'


@pytest.mark.asyncio
@pytest.mark.parametrize('principal', [PrincipalType.PLUGIN, PrincipalType.PROCESSOR])
async def test_ungranted_callers_are_denied(principal):
    ap = app('ja_JP')
    with pytest.raises(ApplicationAPIException) as raised:
        await ap.application_api.execute(OPERATION, agent_context(principal, {'stats.basic'}), {})
    assert raised.value.error.status_code == 403


@pytest.mark.asyncio
async def test_arguments_are_rejected():
    ap = app('ja_JP')
    with pytest.raises(ApplicationAPIException) as raised:
        await ap.application_api.execute(
            OPERATION, agent_context(PrincipalType.PLUGIN, {OPERATION}), {'workspace_uuid': 'workspace-b'}
        )
    assert raised.value.error.code == 'invalid_input'


@pytest.mark.asyncio
async def test_agent_tools_expose_and_call_language_get_only_when_granted():
    ap = app('vi_VN')
    context = agent_context(PrincipalType.PROCESSOR, {OPERATION})
    assert [op.id for op in list_granted(ap, context, consumer='processor', granted=[OPERATION])] == [OPERATION]
    assert list_granted(ap, context, consumer='processor', granted=['workspace.language.update']) == []
    result = await call(ap, context, OPERATION, {}, consumer='processor', granted=[OPERATION])
    assert result['ok'], result
    assert result['result']['language'] == 'vi_VN'
