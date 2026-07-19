from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
import sqlalchemy
import jwt
from quart import Quart
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.workspaces import (
    InvitationsRouterGroup,
    WorkspacesRouterGroup,
)
from langbot.pkg.api.http.controller.groups.apikeys import ApiKeysRouterGroup
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.api.http.service.user import ControlPlaneDirectoryRequiredError, UserService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionState,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.service import WorkspaceService
from langbot.pkg.workspace.policy import CloudWorkspacePolicy


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _PersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    def get_db_engine(self):
        return self.engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    @staticmethod
    def serialize_model(model, row, masked_columns=()):
        return {
            column.name: getattr(row, column.name)
            for column in model.__table__.columns
            if column.name not in masked_columns
        }


@pytest.fixture
async def workspace_api(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "workspace-api.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    application = SimpleNamespace()
    application.persistence_mgr = _PersistenceManager(engine)
    application.instance_config = SimpleNamespace(
        data={
            'system': {
                'jwt': {'secret': 'workspace-api-secret', 'expire': 3600},
                'allow_modify_login_info': True,
            },
            'api': {'global_api_key': ''},
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

    owner = await application.user_service.create_initial_account(
        'owner@example.com',
        'owner-password',
    )
    owner_token = await application.user_service.generate_jwt_token(owner)

    quart_app = Quart(__name__)
    await WorkspacesRouterGroup(application, quart_app).initialize()
    await InvitationsRouterGroup(application, quart_app).initialize()
    await ApiKeysRouterGroup(application, quart_app).initialize()
    await UserRouterGroup(application, quart_app).initialize()

    yield application, quart_app.test_client(), engine, owner_token
    await engine.dispose()


def _auth(token: str, workspace_uuid: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if workspace_uuid is not None:
        headers['X-Workspace-Id'] = workspace_uuid
    return headers


async def test_owner_invites_second_account_and_secret_is_not_persisted(workspace_api):
    application, client, engine, owner_token = workspace_api

    current_response = await client.get('/api/v1/workspaces/current', headers=_auth(owner_token))
    assert current_response.status_code == 200
    current = (await current_response.get_json())['data']
    workspace_uuid = current['workspace']['uuid']
    assert current['membership']['role'] == 'owner'
    assert 'member.invite' in current['permissions']

    invite_response = await client.post(
        f'/api/v1/workspaces/{workspace_uuid}/invitations',
        headers=_auth(owner_token, workspace_uuid),
        json={'email': 'member@example.com', 'role': 'viewer'},
    )
    assert invite_response.status_code == 200
    invite_data = (await invite_response.get_json())['data']
    invitation_token = invite_data['token']
    assert invitation_token.startswith('lbi_')
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
    member_auth = (await accept_response.get_json())['data']
    assert member_auth['workspace_uuid'] == workspace_uuid

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
        headers=_auth(member_auth['token'], workspace_uuid),
    )
    assert member_current_response.status_code == 200
    member_current = (await member_current_response.get_json())['data']
    assert member_current['membership']['role'] == 'viewer'
    assert 'member.invite' not in member_current['permissions']

    forbidden_invite = await client.post(
        f'/api/v1/workspaces/{workspace_uuid}/invitations',
        headers=_auth(member_auth['token'], workspace_uuid),
        json={'email': 'third@example.com', 'role': 'viewer'},
    )
    assert forbidden_invite.status_code == 403
    assert (await forbidden_invite.get_json())['code'] == 'permission_denied'


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
    viewer_token = (await accept_response.get_json())['data']['token']
    forbidden = await client.post(
        '/api/v1/apikeys',
        headers=_auth(viewer_token, workspace_uuid),
        json={'name': 'forbidden'},
    )
    assert forbidden.status_code == 403
    assert (await forbidden.get_json())['code'] == 'permission_denied'


async def test_cloud_projection_is_selected_explicitly_and_directory_writes_use_control_plane(
    workspace_api,
):
    application, client, engine, owner_token = workspace_api
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

    current_response = await client.get(
        '/api/v1/workspaces/current',
        headers=_auth(owner_token, cloud_workspace_uuid),
    )
    assert current_response.status_code == 200
    current = (await current_response.get_json())['data']
    assert current['workspace']['uuid'] == cloud_workspace_uuid
    assert current['workspace']['source'] == 'cloud_projection'
    assert current['placement_generation'] == 12

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
    assert create_invitation.status_code == 409
    assert (await create_invitation.get_json())['code'] == 'control_plane_required'


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
