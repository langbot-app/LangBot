from __future__ import annotations

import datetime
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy
import jwt
from quart import Quart
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.workspaces import (
    InvitationsRouterGroup,
    WorkspacesRouterGroup,
)
from langbot.pkg.api.http.controller.groups.system import SystemRouterGroup
from langbot.pkg.api.http.controller.groups.apikeys import ApiKeysRouterGroup
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.api.http.service.user import ControlPlaneDirectoryRequiredError, UserService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence import apikey
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionState,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.service import WorkspaceService
from langbot.pkg.workspace.policy import CloudWorkspacePolicy


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def workspace_api(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "workspace-api.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    application = SimpleNamespace()
    application.persistence_mgr = PersistenceManager(application)
    application.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
    application.instance_config = SimpleNamespace(
        data={
            'system': {
                'jwt': {'secret': 'workspace-api-secret', 'expire': 3600},
                'allow_modify_login_info': True,
            },
            'api': {'global_api_key': '', 'webui_url': 'https://langbot.example'},
        }
    )
    application.logger = logging.getLogger('workspace-api-test')
    application.workspace_service = WorkspaceService(
        application,
        instance_uuid='instance-workspace-api',
    )
    await application.workspace_service.ensure_singleton_workspace()
    application.workspace_collaboration_service = WorkspaceCollaborationService(
        application,
        application.workspace_service,
    )
    application.user_service = UserService(application)
    application.apikey_service = ApiKeyService(application)

    quart_app = Quart(__name__)
    await WorkspacesRouterGroup(application, quart_app).initialize()
    await InvitationsRouterGroup(application, quart_app).initialize()
    await ApiKeysRouterGroup(application, quart_app).initialize()
    await UserRouterGroup(application, quart_app).initialize()
    await SystemRouterGroup(application, quart_app).initialize()

    client = quart_app.test_client()
    init_response = await client.post(
        '/api/v1/user/init',
        json={'user': 'owner@example.com', 'password': 'owner-password'},
    )
    assert init_response.status_code == 200
    auth_response = await client.post(
        '/api/v1/user/auth',
        json={'user': 'owner@example.com', 'password': 'owner-password'},
    )
    assert auth_response.status_code == 200
    owner_token = (await auth_response.get_json())['data']['token']

    yield application, client, engine, owner_token
    await engine.dispose()


def _auth(token: str, workspace_uuid: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if workspace_uuid is not None:
        headers['X-Workspace-Id'] = workspace_uuid
    return headers


async def test_account_bootstrap_uses_the_account_resolved_from_the_token(workspace_api):
    application, client, _, owner_token = workspace_api
    account = await application.user_service.get_authenticated_account(owner_token)

    application.user_service.get_authenticated_account = AsyncMock(return_value=account)
    application.user_service.get_user_by_email = AsyncMock(return_value=None)

    response = await client.get('/api/v1/workspaces/bootstrap', headers=_auth(owner_token))

    assert response.status_code == 200
    application.user_service.get_user_by_email.assert_not_awaited()


async def test_fresh_sqlite_login_returns_current_workspace_and_user_info(workspace_api):
    _, client, _, owner_token = workspace_api

    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    assert current_response.status_code == 200
    current = (await current_response.get_json())['data']
    assert current['workspace']['uuid']
    assert current['membership']['email'] == 'owner@example.com'
    assert current['membership']['role'] == 'owner'

    info_response = await client.get('/api/v1/user/info', headers=_auth(owner_token))
    assert info_response.status_code == 200
    info = (await info_response.get_json())['data']
    assert info['account_uuid'] == current['membership']['account_uuid']
    assert info['user'] == 'owner@example.com'


async def test_user_info_uses_the_account_resolved_from_the_token(workspace_api):
    application, client, _, owner_token = workspace_api
    account = await application.user_service.get_authenticated_account(owner_token)

    application.user_service.get_authenticated_account = AsyncMock(return_value=account)
    application.user_service.get_user_by_email = AsyncMock(return_value=None)

    response = await client.get('/api/v1/user/info', headers=_auth(owner_token))

    assert response.status_code == 200
    info = (await response.get_json())['data']
    assert info['account_uuid'] == account.uuid
    assert info['user'] == account.user
    application.user_service.get_user_by_email.assert_not_awaited()


async def test_authenticated_system_info_reads_workspace_wizard_metadata(workspace_api):
    application, client, _, owner_token = workspace_api

    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    workspace_uuid = (await current_response.get_json())['data']['workspace']['uuid']
    progress = {'step': 3, 'selected_adapter': 'telegram'}
    await application.persistence_mgr.execute_async(
        sqlalchemy.insert(WorkspaceMetadata),
        [
            {
                'workspace_uuid': workspace_uuid,
                'key': 'wizard_status',
                'value': 'completed',
            },
            {
                'workspace_uuid': workspace_uuid,
                'key': 'wizard_progress',
                'value': json.dumps(progress),
            },
        ],
    )

    response = await client.get(
        '/api/v1/system/info',
        headers=_auth(owner_token, workspace_uuid),
    )

    assert response.status_code == 200
    data = (await response.get_json())['data']
    assert data['wizard_status'] == 'completed'
    assert data['wizard_progress'] == progress


async def test_owner_invites_second_account_and_secret_is_not_persisted(workspace_api):
    application, client, engine, owner_token = workspace_api

    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    assert current_response.status_code == 200
    current = (await current_response.get_json())['data']
    workspace_uuid = current['workspace']['uuid']
    assert current['membership']['role'] == 'owner'
    assert 'member.invite' in current['permissions']
    assert 'owner.transfer' not in current['permissions']

    invite_response = await client.post(
        f'/api/v1/workspaces/{workspace_uuid}/invitations',
        headers=_auth(owner_token, workspace_uuid),
        json={'email': 'member@example.com', 'role': 'viewer'},
    )
    assert invite_response.status_code == 200
    invite_data = (await invite_response.get_json())['data']
    invitation_token = invite_data['token']
    assert invitation_token.startswith('lbi_')
    assert invite_data['link'] == f'https://langbot.example/invitations/accept#token={invitation_token}'
    assert invite_data['delivery'] == {'status': 'link_only', 'provider': None}
    assert 'token_hash' not in invite_data['invitation']

    async with engine.connect() as connection:
        persisted_token_hash = await connection.scalar(
            sqlalchemy.select(WorkspaceInvitation.token_hash).where(
                WorkspaceInvitation.uuid == invite_data['invitation']['uuid']
            )
        )
        assert persisted_token_hash is not None
        assert persisted_token_hash != invitation_token

    inspect_response = await client.post(
        '/api/v1/invitations/inspect',
        json={'token': invitation_token},
    )
    assert inspect_response.status_code == 200
    inspected = (await inspect_response.get_json())['data']
    assert inspected['workspace']['uuid'] == workspace_uuid
    assert inspected['invitation']['normalized_email'] == 'member@example.com'

    accept_response = await client.post(
        '/api/v1/invitations/accept',
        json={
            'token': invitation_token,
            'registration': {
                'email': 'member@example.com',
                'password': 'member-password',
            },
        },
    )
    assert accept_response.status_code == 200
    member_registration = (await accept_response.get_json())['data']
    assert member_registration == {'workspace_uuid': workspace_uuid, 'login_required': True}

    member_login_response = await client.post(
        '/api/v1/user/auth',
        json={'user': 'member@example.com', 'password': 'member-password'},
    )
    assert member_login_response.status_code == 200
    member_token = (await member_login_response.get_json())['data']['token']

    reused_response = await client.post(
        '/api/v1/invitations/accept',
        json={
            'token': invitation_token,
            'registration': {
                'email': 'member@example.com',
                'password': 'member-password',
            },
        },
    )
    assert reused_response.status_code == 400
    assert (await reused_response.get_json())['code'] == 'invitation_used'

    member_current_response = await client.get(
        '/api/v1/workspaces/current',
        headers=_auth(member_token, workspace_uuid),
    )
    assert member_current_response.status_code == 200
    member_current = (await member_current_response.get_json())['data']
    assert member_current['membership']['role'] == 'viewer'
    assert 'member.invite' not in member_current['permissions']

    transfer_response = await client.patch(
        f'/api/v1/workspaces/{workspace_uuid}/members/{member_current["membership"]["account_uuid"]}',
        headers=_auth(owner_token, workspace_uuid),
        json={'role': 'owner'},
    )
    assert transfer_response.status_code == 403
    assert (await transfer_response.get_json())['code'] == 'permission_denied'

    forbidden_invite = await client.post(
        f'/api/v1/workspaces/{workspace_uuid}/invitations',
        headers=_auth(member_token, workspace_uuid),
        json={'email': 'third@example.com', 'role': 'viewer'},
    )
    assert forbidden_invite.status_code == 403
    assert (await forbidden_invite.get_json())['code'] == 'permission_denied'


async def test_workspace_member_list_returns_display_name_and_email(workspace_api):
    _, client, engine, owner_token = workspace_api

    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    current = (await current_response.get_json())['data']
    workspace_uuid = current['workspace']['uuid']
    owner_uuid = current['membership']['account_uuid']

    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.update(User).where(User.uuid == owner_uuid).values(user='Owner Display Name')
        )

    response = await client.get(
        f'/api/v1/workspaces/{workspace_uuid}/members',
        headers=_auth(owner_token, workspace_uuid),
    )

    assert response.status_code == 200
    members = (await response.get_json())['data']['members']
    assert len(members) == 1
    assert members[0]['display_name'] == 'Owner Display Name'
    assert members[0]['email'] == 'owner@example.com'


async def test_oss_invitation_accept_requires_logout_before_registration(workspace_api):
    _, client, _, owner_token = workspace_api

    response = await client.post(
        '/api/v1/invitations/accept',
        headers={'Authorization': f'Bearer {owner_token}'},
        json={'token': 'lbi_pending-invitation'},
    )

    assert response.status_code == 409
    assert (await response.get_json())['code'] == 'invitation_logout_required'


async def test_invalid_bearer_on_cloud_invitation_is_authentication_failure(workspace_api):
    application, client, _, _ = workspace_api
    application.deployment = SimpleNamespace(mode='cloud')

    response = await client.post(
        '/api/v1/invitations/accept',
        headers={'Authorization': 'Bearer definitely-not-a-jwt'},
        json={'token': 'lbi_not-a-real-invitation'},
    )

    assert response.status_code == 401
    assert await response.get_json() == {
        'code': 'invalid_authentication',
        'msg': 'Invalid authentication credentials',
    }


async def test_workspace_selector_and_path_cannot_escape_membership(workspace_api):
    _, client, _, owner_token = workspace_api

    unknown_uuid = '00000000-0000-0000-0000-000000000099'
    selector_response = await client.get(
        '/api/v1/workspaces/current',
        headers=_auth(owner_token, unknown_uuid),
    )
    assert selector_response.status_code == 404
    assert (await selector_response.get_json())['code'] == 'resource_not_found'

    path_response = await client.get(
        f'/api/v1/workspaces/{unknown_uuid}',
        headers=_auth(owner_token),
    )
    assert path_response.status_code == 404
    assert (await path_response.get_json())['code'] == 'resource_not_found'


async def test_oss_rejects_second_workspace(workspace_api):
    _, client, _, owner_token = workspace_api

    response = await client.post('/api/v1/workspaces', headers=_auth(owner_token), json={'name': 'Second'})
    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'edition_limit'


async def test_jwt_uses_account_uuid_and_disabled_account_is_rejected(workspace_api):
    _, client, engine, owner_token = workspace_api
    payload = jwt.decode(
        owner_token,
        'workspace-api-secret',
        algorithms=['HS256'],
        audience='langbot-instance:instance-workspace-api',
        issuer='langbot-core',
    )
    assert payload['sub']
    assert payload['sub'] != payload['user']

    async with engine.begin() as connection:
        await connection.execute(sqlalchemy.update(User).where(User.uuid == payload['sub']).values(status='disabled'))

    response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    assert response.status_code == 401
    assert (await response.get_json())['code'] == 'invalid_authentication'


async def test_api_key_secret_is_one_time_and_viewer_cannot_manage_keys(workspace_api):
    application, client, _engine, owner_token = workspace_api
    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    workspace_uuid = (await current_response.get_json())['data']['workspace']['uuid']

    create_response = await client.post(
        '/api/v1/apikeys',
        headers=_auth(owner_token, workspace_uuid),
        json={'name': 'E2E automation', 'scopes': ['resource.view']},
    )
    assert create_response.status_code == 200
    created = (await create_response.get_json())['data']['key']
    assert created['key'].startswith('lbk_')
    assert created['secret_available'] is True
    assert 'key_hash' not in created

    list_response = await client.get('/api/v1/apikeys', headers=_auth(owner_token, workspace_uuid))
    listed = (await list_response.get_json())['data']['keys']
    assert len(listed) == 1
    assert 'key' not in listed[0]
    assert 'key_hash' not in listed[0]
    assert listed[0]['secret_available'] is False
    identity = await application.apikey_service.authenticate_api_key(created['key'])
    assert identity is not None
    assert identity.workspace_uuid == workspace_uuid
    assert identity.permissions == frozenset({'resource.view'})

    invite_response = await client.post(
        f'/api/v1/workspaces/{workspace_uuid}/invitations',
        headers=_auth(owner_token, workspace_uuid),
        json={'email': 'viewer@example.com', 'role': 'viewer'},
    )
    invitation_token = (await invite_response.get_json())['data']['token']
    accept_response = await client.post(
        '/api/v1/invitations/accept',
        json={
            'token': invitation_token,
            'registration': {'email': 'viewer@example.com', 'password': 'viewer-password'},
        },
    )
    assert accept_response.status_code == 200
    assert (await accept_response.get_json())['data']['login_required'] is True
    login_response = await client.post(
        '/api/v1/user/auth',
        json={'user': 'viewer@example.com', 'password': 'viewer-password'},
    )
    assert login_response.status_code == 200
    viewer_token = (await login_response.get_json())['data']['token']
    forbidden = await client.post(
        '/api/v1/apikeys',
        headers=_auth(viewer_token, workspace_uuid),
        json={'name': 'forbidden'},
    )
    assert forbidden.status_code == 403
    assert (await forbidden.get_json())['code'] == 'permission_denied'


async def test_api_key_context_returns_bound_identity_without_workspace_permission(workspace_api):
    application, client, _, owner_token = workspace_api
    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    workspace_uuid = (await current_response.get_json())['data']['workspace']['uuid']

    create_response = await client.post(
        '/api/v1/apikeys',
        headers=_auth(owner_token, workspace_uuid),
        json={'name': 'Context probe', 'scopes': []},
    )
    assert create_response.status_code == 200
    created = (await create_response.get_json())['data']['key']

    missing_auth = await client.get('/api/v1/system/context')
    assert missing_auth.status_code == 401

    invalid_auth = await client.get(
        '/api/v1/system/context',
        headers={'X-API-Key': 'lbk_invalid'},
    )
    assert invalid_auth.status_code == 401

    invalid_capabilities = await client.get(
        '/api/v1/system/capabilities',
        headers={'X-API-Key': 'lbk_invalid'},
    )
    assert invalid_capabilities.status_code == 401

    response = await client.get(
        '/api/v1/system/context',
        headers={
            'X-API-Key': created['key'],
            'X-Workspace-Id': 'caller-selected-workspace-must-be-ignored',
        },
    )

    assert response.status_code == 200
    assert (await response.get_json())['data'] == {
        'instance_uuid': application.workspace_service.instance_uuid,
        'workspace_uuid': workspace_uuid,
        'api_key_id': created['uuid'],
        'permissions': [],
    }

    capabilities_response = await client.get(
        '/api/v1/system/capabilities',
        headers={
            'X-API-Key': created['key'],
            'X-Workspace-Id': 'caller-selected-workspace-must-be-ignored',
        },
    )
    assert capabilities_response.status_code == 200
    capabilities = (await capabilities_response.get_json())['data']
    assert capabilities['schema_version'] == 1
    assert sorted(capabilities['operations']) == sorted(
        [
            'bot.list',
            'bot.get',
            'bot.create',
            'bot.update',
            'bot.delete',
            'pipeline.list',
            'pipeline.get',
            'pipeline.create',
            'pipeline.update',
            'pipeline.delete',
            'pipeline.copy',
            'task.list',
            'task.get',
            'knowledge_base.get',
            'knowledge_base.file.store',
            'knowledge_base.retrieve',
            'file.document.upload',
            'plugin.install.github',
            'plugin.install.marketplace',
            'plugin.install.local',
            'plugin.upgrade',
            'plugin.get',
            'plugin.list',
            'plugin.config.get',
            'plugin.logs',
            'skill.list',
            'skill.get',
            'skill.files.list',
            'skill.files.read',
            'skill.preview',
            'skill.install.github',
            'skill.install.upload',
            'mcp_server.list',
            'mcp_server.get',
            'mcp_server.resources',
            'mcp_server.resource_templates',
            'mcp_server.resource_read',
            'mcp_server.logs',
            'mcp_server.test',
        ]
    )
    assert all(item == {'supported': True} for item in capabilities['operations'].values())
    assert created['key'] not in await capabilities_response.get_data(as_text=True)

    bearer_response = await client.get(
        '/api/v1/system/context',
        headers={'Authorization': f'Bearer {created["key"]}'},
    )
    assert bearer_response.status_code == 200
    assert (await bearer_response.get_json())['data']['api_key_id'] == created['uuid']

    jwt_response = await client.get(
        '/api/v1/system/context',
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert jwt_response.status_code == 401

    await application.persistence_mgr.execute_async(
        sqlalchemy.update(apikey.ApiKey)
        .where(apikey.ApiKey.uuid == created['uuid'])
        .values(expires_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(seconds=1))
    )
    expired_capabilities = await client.get(
        '/api/v1/system/capabilities',
        headers={'X-API-Key': created['key']},
    )
    assert expired_capabilities.status_code == 401

    revoke_response = await client.delete(
        f'/api/v1/apikeys/{created["id"]}',
        headers=_auth(owner_token, workspace_uuid),
    )
    assert revoke_response.status_code == 200

    revoked_response = await client.get(
        '/api/v1/system/context',
        headers={'X-API-Key': created['key']},
    )
    assert revoked_response.status_code == 401
    revoked_capabilities = await client.get(
        '/api/v1/system/capabilities',
        headers={'X-API-Key': created['key']},
    )
    assert revoked_capabilities.status_code == 401


async def test_api_key_can_query_tasks_with_public_contract_and_resource_permission(workspace_api):
    application, client, _, owner_token = workspace_api
    task_query = {}
    task_lookup = {}
    fake_task = SimpleNamespace(
        to_public_dict=lambda: {'id': 7, 'status': 'running', 'error': None, 'result': None},
        to_dict=lambda: {'id': 7, 'runtime': {'state': 'PENDING'}},
    )

    def get_tasks_dict(*args, **kwargs):
        task_query.update(kwargs)
        if kwargs.get('public'):
            return {'tasks': []}
        return {'tasks': [], 'id_index': 1}

    def get_task_by_id(*args, **kwargs):
        task_lookup.update(kwargs)
        return fake_task if args and args[0] == 7 else None

    application.task_mgr = SimpleNamespace(
        get_tasks_dict=get_tasks_dict,
        get_task_by_id=get_task_by_id,
    )
    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    workspace_uuid = (await current_response.get_json())['data']['workspace']['uuid']
    create_response = await client.post(
        '/api/v1/apikeys',
        headers=_auth(owner_token, workspace_uuid),
        json={'name': 'Task reader', 'scopes': ['resource.view']},
    )
    assert create_response.status_code == 200
    key = (await create_response.get_json())['data']['key']['key']

    listing = await client.get('/api/v1/system/tasks', headers={'X-API-Key': key})
    assert listing.status_code == 200
    assert (await listing.get_json())['data'] == {'tasks': []}
    assert task_query['instance_uuid'] == application.workspace_service.instance_uuid
    assert task_query['workspace_uuid'] == workspace_uuid
    assert task_query['placement_generation'] == 1
    assert task_query['public'] is True

    bearer_listing = await client.get('/api/v1/system/tasks', headers=_auth(owner_token, workspace_uuid))
    assert bearer_listing.status_code == 200
    assert (await bearer_listing.get_json())['data'] == {'tasks': [], 'id_index': 1}

    public_task = await client.get('/api/v1/system/tasks/7', headers={'X-API-Key': key})
    assert public_task.status_code == 200
    assert (await public_task.get_json())['data'] == {
        'id': 7,
        'status': 'running',
        'error': None,
        'result': None,
    }
    assert task_lookup == {
        'instance_uuid': application.workspace_service.instance_uuid,
        'workspace_uuid': workspace_uuid,
        'placement_generation': 1,
    }

    legacy_task = await client.get('/api/v1/system/tasks/7', headers=_auth(owner_token, workspace_uuid))
    assert legacy_task.status_code == 200
    assert (await legacy_task.get_json())['data'] == {'id': 7, 'runtime': {'state': 'PENDING'}}

    missing = await client.get('/api/v1/system/tasks/not-an-id', headers={'X-API-Key': key})
    assert missing.status_code == 404

    no_permission_response = await client.post(
        '/api/v1/apikeys',
        headers=_auth(owner_token, workspace_uuid),
        json={'name': 'Task denied', 'scopes': []},
    )
    assert no_permission_response.status_code == 200
    no_permission_key = (await no_permission_response.get_json())['data']['key']['key']
    denied = await client.get('/api/v1/system/tasks', headers={'X-API-Key': no_permission_key})
    assert denied.status_code == 403


async def test_cloud_projection_is_selected_explicitly_and_collaboration_runs_in_core(
    workspace_api,
):
    application, client, engine, owner_token = workspace_api
    application.deployment = SimpleNamespace(mode='cloud')
    owner_uuid = jwt.decode(
        owner_token,
        'workspace-api-secret',
        algorithms=['HS256'],
        audience='langbot-instance:instance-workspace-api',
        issuer='langbot-core',
    )['sub']
    cloud_workspace_uuid = '00000000-0000-0000-0000-000000000777'

    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.insert(Workspace).values(
                uuid=cloud_workspace_uuid,
                instance_uuid='instance-workspace-api',
                name='Cloud Team',
                slug='cloud-team',
                type='team',
                status='active',
                source='cloud_projection',
                projection_revision=12,
            )
        )
        await connection.execute(
            sqlalchemy.insert(WorkspaceExecutionState).values(
                workspace_uuid=cloud_workspace_uuid,
                instance_uuid='instance-workspace-api',
                active_generation=12,
                state='active',
                write_fenced=False,
                source='cloud',
                desired_state_revision=12,
            )
        )
        await connection.execute(
            sqlalchemy.insert(WorkspaceMembership).values(
                uuid='00000000-0000-0000-0000-000000000778',
                workspace_uuid=cloud_workspace_uuid,
                account_uuid=owner_uuid,
                role='owner',
                status='active',
                projection_revision=12,
            )
        )

    policy = CloudWorkspacePolicy()
    application.workspace_service.policy = policy
    application.workspace_collaboration_service.policy = policy

    with pytest.raises(ControlPlaneDirectoryRequiredError):
        await application.user_service.create_initial_account(
            'forbidden-cloud-local@example.com',
            'password',
        )

    omitted = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    assert omitted.status_code == 404

    refreshed_token = await client.get('/api/v1/user/check-token', headers=_auth(owner_token))
    assert refreshed_token.status_code == 200
    assert (await refreshed_token.get_json())['data']['token']

    bootstrap_response = await client.get(
        '/api/v1/workspaces/bootstrap',
        headers=_auth(owner_token),
    )
    assert bootstrap_response.status_code == 200
    bootstrap = (await bootstrap_response.get_json())['data']
    singleton_uuid = (await application.workspace_service.get_singleton_workspace()).uuid
    workspace_uuids = [item['workspace']['uuid'] for item in bootstrap['workspaces']]
    assert set(workspace_uuids) == {singleton_uuid, cloud_workspace_uuid}
    repeated = await client.get('/api/v1/workspaces/bootstrap', headers=_auth(owner_token))
    assert [item['workspace']['uuid'] for item in (await repeated.get_json())['data']['workspaces']] == workspace_uuids
    by_uuid = {item['workspace']['uuid']: item for item in bootstrap['workspaces']}
    assert by_uuid[singleton_uuid]['membership']['account_uuid'] == owner_uuid
    assert by_uuid[singleton_uuid]['membership']['email'] == 'owner@example.com'
    assert by_uuid[singleton_uuid]['permissions']
    assert by_uuid[cloud_workspace_uuid]['placement_generation'] == 12

    list_response = await client.get(
        '/api/v1/workspaces',
        headers=_auth(owner_token, singleton_uuid),
    )
    assert list_response.status_code == 200
    assert {workspace['uuid'] for workspace in (await list_response.get_json())['data']['workspaces']} == {
        singleton_uuid,
        cloud_workspace_uuid,
    }

    class PlanResolver:
        async def resolve(self, workspace_uuid: str, *, minimum_revision: int = 0):
            from langbot.pkg.cloud.entitlements import EntitlementSnapshot

            assert workspace_uuid == cloud_workspace_uuid
            return EntitlementSnapshot(
                instance_uuid='instance-workspace-api',
                workspace_uuid=workspace_uuid,
                entitlement_revision=max(12, minimum_revision),
                status='active',
                not_before=1,
                expires_at=4102444800,
                plan_name='free',
            )

    application.entitlement_resolver = PlanResolver()
    bootstrap_with_plans = await client.get('/api/v1/workspaces/bootstrap', headers=_auth(owner_token))
    bootstrap_by_uuid = {
        item['workspace']['uuid']: item for item in (await bootstrap_with_plans.get_json())['data']['workspaces']
    }
    assert bootstrap_by_uuid[cloud_workspace_uuid]['plan_name'] == 'free'
    assert bootstrap_by_uuid[singleton_uuid]['plan_name'] is None
    current_response = await client.get(
        '/api/v1/workspaces/current',
        headers=_auth(owner_token, cloud_workspace_uuid),
    )
    assert current_response.status_code == 200
    current = (await current_response.get_json())['data']
    assert current['workspace']['uuid'] == cloud_workspace_uuid
    assert current['workspace']['source'] == 'cloud_projection'
    assert current['placement_generation'] == 12
    assert current['plan_name'] == 'free'

    create_workspace = await client.post(
        '/api/v1/workspaces',
        headers=_auth(owner_token, cloud_workspace_uuid),
        json={'name': 'Not in Core'},
    )
    assert create_workspace.status_code == 409
    assert (await create_workspace.get_json())['code'] == 'control_plane_required'

    create_invitation = await client.post(
        f'/api/v1/workspaces/{cloud_workspace_uuid}/invitations',
        headers=_auth(owner_token, cloud_workspace_uuid),
        json={'email': 'member@example.com', 'role': 'viewer'},
    )
    assert create_invitation.status_code == 200
    created_invitation = (await create_invitation.get_json())['data']
    assert created_invitation['invitation']['workspace_uuid'] == cloud_workspace_uuid
    assert created_invitation['link'].startswith('https://langbot.example/invitations/accept#token=lbi_')
    assert created_invitation['delivery'] == {'status': 'link_only', 'provider': None}

    accept_response = await client.post(
        '/api/v1/invitations/accept',
        headers=_auth(owner_token, cloud_workspace_uuid),
        json={'token': created_invitation['token']},
    )
    assert accept_response.status_code == 400
    assert (await accept_response.get_json())['code'] == 'invitation_email_mismatch'

    registration_response = await client.post(
        '/api/v1/invitations/accept',
        json={
            'token': created_invitation['token'],
            'registration': {'email': 'member@example.com', 'password': 'member-password'},
        },
    )
    assert registration_response.status_code == 401
    assert (await registration_response.get_json())['code'] == 'account_exists_login_required'


async def test_account_bootstrap_does_not_disclose_non_member_workspaces(workspace_api):
    application, client, engine, owner_token = workspace_api
    foreign_workspace_uuid = '00000000-0000-0000-0000-000000000880'

    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.insert(Workspace).values(
                uuid=foreign_workspace_uuid,
                instance_uuid='instance-workspace-api',
                name='Foreign Team',
                slug='foreign-team',
                type='team',
                status='active',
                source='cloud_projection',
                projection_revision=1,
            )
        )
        await connection.execute(
            sqlalchemy.insert(WorkspaceExecutionState).values(
                workspace_uuid=foreign_workspace_uuid,
                instance_uuid='instance-workspace-api',
                active_generation=1,
                state='active',
                write_fenced=False,
                source='cloud',
                desired_state_revision=1,
            )
        )

    policy = CloudWorkspacePolicy()
    application.workspace_service.policy = policy
    application.workspace_collaboration_service.policy = policy

    response = await client.get('/api/v1/workspaces/bootstrap', headers=_auth(owner_token))
    assert response.status_code == 200
    workspace_uuids = {item['workspace']['uuid'] for item in (await response.get_json())['data']['workspaces']}
    assert foreign_workspace_uuid not in workspace_uuids

    current = await client.get(
        '/api/v1/workspaces/current',
        headers=_auth(owner_token, foreign_workspace_uuid),
    )
    assert current.status_code == 404
    assert (await current.get_json())['code'] == 'resource_not_found'
