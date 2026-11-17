import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.context import PrincipalType, RequestContext
from langbot.pkg.api.http.authz import Permission, permissions_for_role
from langbot.pkg.api.http.controller.group import AuthType, RouterGroup
from langbot.pkg.persistence.mgr import PersistenceMode
from langbot.pkg.telemetry import heartbeat, usage


@pytest.fixture(autouse=True)
def reset_usage(monkeypatch):
    monkeypatch.setattr(usage, 'GROUPS', usage.GROUPS | {'knowledge'})
    usage._workspaces.clear()
    yield
    usage._workspaces.clear()


@pytest.fixture(params=[PersistenceMode.OSS_COMPAT, PersistenceMode.CLOUD_RUNTIME])
def ap(request):
    async def authenticate_account(token):
        if token != 'user-token':
            raise ValueError('Invalid user token')
        return SimpleNamespace(uuid='account', user='user@example.test')

    async def resolve_workspace(account_uuid, workspace_uuid):
        assert account_uuid == 'account'
        assert workspace_uuid in ('workspace-a', 'workspace-b')
        return SimpleNamespace(
            workspace=SimpleNamespace(uuid=workspace_uuid),
            membership=SimpleNamespace(uuid='member', role='owner', projection_revision=1),
            execution=SimpleNamespace(instance_uuid='instance', placement_generation=1),
        )

    async def authenticate_api_key(token):
        if token not in ('key-workspace-a', 'key-workspace-b'):
            raise ValueError('Invalid API key')
        return SimpleNamespace(
            instance_uuid='instance',
            workspace_uuid=token.removeprefix('key-'),
            api_key_uuid=token,
            placement_generation=1,
            permissions=permissions_for_role('owner'),
        )

    async def authenticate_support(token, *, requested_workspace_uuid):
        assert token == 'support-token'
        assert requested_workspace_uuid in ('workspace-a', 'workspace-b')
        return SimpleNamespace(
            instance_uuid='instance',
            workspace_uuid=requested_workspace_uuid,
            placement_generation=1,
            actor_account_uuid='support-account',
            grant_jti_hash='support-session',
        )

    return SimpleNamespace(
        instance_config=SimpleNamespace(data={'space': {}}),
        persistence_mgr=SimpleNamespace(mode=request.param, execute_async=AsyncMock()),
        deployment=SimpleNamespace(multi_workspace_enabled=True),
        entitlement_resolver=SimpleNamespace(
            instance_uuid='instance', resolve=AsyncMock(return_value=SimpleNamespace(entitlement_revision=1))
        ),
        user_service=SimpleNamespace(get_authenticated_account=AsyncMock(side_effect=authenticate_account)),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(side_effect=resolve_workspace)
        ),
        apikey_service=SimpleNamespace(authenticate_api_key=AsyncMock(side_effect=authenticate_api_key)),
        support_admin_session_service=SimpleNamespace(
            is_support_admin_token=lambda token: token == 'support-token',
            authenticate_token=AsyncMock(side_effect=authenticate_support),
        ),
    )


class UsageGroup(RouterGroup):
    name, path = 'knowledge', '/api/v1/knowledge'

    async def initialize(self):
        pass


def register_route(ap, auth_type, *, permission=None, fail=False):
    app = quart.Quart(__name__)
    group = UsageGroup(ap, app)

    @group.route('/bases', auth_type=auth_type, permission=permission)
    async def endpoint(request_context=None):
        await asyncio.sleep(0)
        if auth_type == AuthType.ACCOUNT_TOKEN:
            assert request_context is None
        else:
            assert isinstance(request_context, RequestContext)
            assert request_context.workspace_uuid == quart.request.headers['X-Workspace-Id']
        if fail:
            raise ValueError('Handler failed')
        return group.success()

    return app, group


AUTH_CASES = [
    (AuthType.USER_TOKEN, 'user', PrincipalType.ACCOUNT, 'webui'),
    (AuthType.API_KEY, 'key-header', PrincipalType.API_KEY, 'lbctl'),
    (AuthType.API_KEY, 'key-bearer', PrincipalType.API_KEY, 'lbctl'),
    (AuthType.USER_TOKEN_OR_API_KEY, 'user', PrincipalType.ACCOUNT, 'webui'),
    (AuthType.USER_TOKEN_OR_API_KEY, 'key-header', PrincipalType.API_KEY, 'lbctl'),
    (AuthType.USER_TOKEN_OR_API_KEY, 'key-bearer', PrincipalType.API_KEY, 'lbctl'),
    (AuthType.USER_TOKEN, 'support', PrincipalType.SUPPORT_ADMIN, 'webui'),
    (AuthType.USER_TOKEN_OR_API_KEY, 'support', PrincipalType.SUPPORT_ADMIN, 'webui'),
]


def headers_for(workspace_uuid, credential, lbctl=True):
    headers = {
        'X-Workspace-Id': workspace_uuid,
        'User-Agent': 'lbctl/0.4.1 (darwin/arm64)' if lbctl else 'custom-client',
        'X-LangBot-Client-Command': 'knowledge-base.list',
    }
    if credential == 'key-header':
        headers['X-API-Key'] = f'key-{workspace_uuid}'
    else:
        headers['Authorization'] = 'Bearer ' + (
            f'key-{workspace_uuid}' if credential == 'key-bearer' else f'{credential}-token'
        )
    return headers


@pytest.mark.parametrize('auth_type,credential,principal,client', AUTH_CASES)
@pytest.mark.parametrize('lbctl', [False, True])
async def test_authenticated_workspaces_reach_heartbeat(
    ap, auth_type, credential, principal, client, lbctl, monkeypatch
):
    assert not hasattr(ap, '_telemetry_default_workspace')
    app, _group = register_route(ap, auth_type)
    observed_contexts = []
    record_http = usage.record_http

    def record_with_context(application, context, *args, **kwargs):
        assert isinstance(context, RequestContext)
        assert context.principal.principal_type is principal
        observed_contexts.append(context)
        record_http(application, context, *args, **kwargs)

    monkeypatch.setattr(usage, 'record_http', record_with_context)
    workspaces = ('workspace-a', 'workspace-b')
    responses = await asyncio.gather(
        *(
            app.test_client().get('/api/v1/knowledge/bases', headers=headers_for(ws, credential, lbctl))
            for ws in workspaces
        )
    )
    assert [response.status_code for response in responses] == [200, 200]
    assert {context.workspace_uuid for context in observed_contexts} == set(workspaces)
    for workspace_uuid in workspaces:
        entries = usage.take_batch(workspace_uuid)['c']
        expected_client = 'api_other' if client == 'lbctl' and not lbctl else client
        assert entries[0] == [
            'api.call',
            {'group': 'knowledge', 'method': 'GET', 'client': expected_client, 'status': '2xx'},
            1,
        ]
        if expected_client == 'lbctl':
            assert entries[1:] == [
                ['lbctl.cmd', {'cmd': 'knowledge-base.list', 'status': '2xx'}, 1],
                ['lbctl.client', {'version': '0.4.1', 'os': 'darwin'}, 1],
            ]
        else:
            assert len(entries) == 1
        payload = await heartbeat.build_heartbeat_payload(ap, workspace_uuid=workspace_uuid, workspace_resource={})
        assert payload['features']['usage']['c'] == entries
    if ap.persistence_mgr.mode == PersistenceMode.CLOUD_RUNTIME:
        ap.persistence_mgr.execute_async.assert_not_awaited()


@pytest.mark.parametrize('auth_type,credential,principal,client', AUTH_CASES)
async def test_route_publishes_resolved_context(ap, auth_type, credential, principal, client, monkeypatch):
    app, group = register_route(ap, auth_type)
    method = (
        '_authenticate_api_key'
        if principal == PrincipalType.API_KEY
        else '_authenticate_support_admin'
        if principal == PrincipalType.SUPPORT_ADMIN
        else '_resolve_account_context'
    )
    resolve = getattr(group, method)

    async def resolve_without_publishing(*args, **kwargs):
        context = await resolve(*args, **kwargs)
        quart.g.pop('request_context', None)
        return context

    monkeypatch.setattr(group, method, resolve_without_publishing)
    response = await app.test_client().get('/api/v1/knowledge/bases', headers=headers_for('workspace-a', credential))
    assert response.status_code == 200
    assert usage.take_batch('workspace-a')['c'][0][1]['client'] == client


@pytest.mark.parametrize('auth_type', [AuthType.USER_TOKEN, AuthType.API_KEY, AuthType.USER_TOKEN_OR_API_KEY])
async def test_untrusted_workspace_is_not_counted(ap, auth_type):
    app, _group = register_route(ap, auth_type)
    for headers in ({'X-Workspace-Id': 'workspace-a'}, headers_for('workspace-b', 'invalid')):
        response = await app.test_client().get('/api/v1/knowledge/bases', headers=headers)
        assert response.status_code == 401
    assert not usage._workspaces


async def test_account_token_does_not_select_workspace(ap):
    app, _group = register_route(ap, AuthType.ACCOUNT_TOKEN)
    response = await app.test_client().get('/api/v1/knowledge/bases', headers=headers_for('workspace-a', 'user'))
    assert response.status_code == 200
    ap.workspace_collaboration_service.resolve_account_workspace.assert_not_awaited()
    assert not usage._workspaces


@pytest.mark.parametrize('failed', [False, True])
async def test_resolved_workspace_errors_are_counted(ap, failed):
    app, _group = register_route(
        ap, AuthType.USER_TOKEN, permission=None if failed else Permission.MEMBER_VIEW, fail=failed
    )
    response = await app.test_client().get('/api/v1/knowledge/bases', headers=headers_for('workspace-a', 'support'))
    assert response.status_code == (500 if failed else 403)
    assert usage.take_batch('workspace-a')['c'][0][1]['status'] == ('5xx' if failed else '4xx')
    assert usage.take_batch('workspace-b') is None
