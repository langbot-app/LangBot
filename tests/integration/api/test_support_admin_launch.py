from __future__ import annotations

import base64
import datetime
import json
import logging
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from quart import Quart
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.api.http.authz import Permission
from langbot.pkg.api.http.context import PrincipalType, RequestContext
from langbot.pkg.api.http.controller import group
from langbot.pkg.api.http.controller.groups.pipelines.websocket_chat import WebSocketChatRouterGroup
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.cloud.launch import SpaceLaunchError, SpaceLaunchService
from langbot.pkg.cloud.support_admin import SupportAdminSessionService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.support_admin import SupportAdminTemporarySession
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionState,
    WorkspaceMembership,
)
from langbot.pkg.workspace.service import WorkspaceService


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


INSTANCE_UUID = 'instance-support-admin'
WORKSPACE_UUID = '10000000-0000-4000-8000-000000000001'
OTHER_WORKSPACE_UUID = '10000000-0000-4000-8000-000000000002'
ACTOR_ACCOUNT_UUID = '20000000-0000-4000-8000-000000000001'
KEY_ID = 'support-admin-key-1'


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _sign(private_key: Ed25519PrivateKey, claims: dict, *, key_id: str = KEY_ID) -> str:
    header = {'alg': 'EdDSA', 'kid': key_id, 'typ': 'langbot-control-plane+jwt'}
    encoded_header = _base64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    encoded_claims = _base64url(json.dumps(claims, separators=(',', ':')).encode('utf-8'))
    signing_input = f'{encoded_header}.{encoded_claims}'
    return f'{signing_input}.{_base64url(private_key.sign(signing_input.encode("ascii")))}'


def _admin_claims(*, now: int, jti: str | None = None, workspace_uuid: str = WORKSPACE_UUID) -> dict:
    return {
        'iss': 'langbot-space',
        'aud': 'langbot-cloud-runtime',
        'sub': f'langbot-instance:{INSTANCE_UUID}',
        'jti': jti or str(uuid.uuid4()),
        'iat': now,
        'nbf': now - 5,
        'exp': now + 90,
        'instance_uuid': INSTANCE_UUID,
        'kind': 'workspace.support_admin_launch',
        'payload': {
            'workspace_uuid': workspace_uuid,
            'launch_mode': 'support_admin',
            'principal_type': 'support_admin',
            'actor_account_uuid': ACTOR_ACCOUNT_UUID,
            'effective_role': 'owner',
        },
    }


@group.group_class('support_admin_probe', '/api/v1/support-admin-probe')
class SupportAdminProbeGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/user-token', auth_type=group.AuthType.USER_TOKEN, permission=Permission.WORKSPACE_VIEW)
        async def _(request_context: RequestContext) -> str:
            return self.success(data=_context_payload(request_context))

        @self.route(
            '/member-operation',
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.MEMBER_VIEW,
        )
        async def member_operation(request_context: RequestContext) -> str:
            return self.success(data=_context_payload(request_context))

        @self.route(
            '/user-token-or-api-key',
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.WORKSPACE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=_context_payload(request_context))


def _context_payload(request_context: RequestContext) -> dict:
    return {
        'principal_type': request_context.principal.principal_type.value,
        'actor_account_uuid': request_context.principal.actor_account_uuid,
        'account_uuid': request_context.principal.account_uuid,
        'role': request_context.workspace.role,
        'membership_uuid': request_context.workspace.membership_uuid,
        'permissions': sorted(request_context.workspace.permissions),
    }


class _TenantUow:
    def __init__(self, engine):
        self._engine = engine
        self.session = None
        self._transaction = None

    async def __aenter__(self):
        session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self.session = session_factory()
        self._transaction = await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self.session.close()


class _TenantScope:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _PersistenceManager:
    def __init__(self, engine):
        self._engine = engine
        self.mode = SimpleNamespace(value='oss_compat')

    def get_db_engine(self):
        return self._engine

    def tenant_uow(self, workspace_uuid: str):
        del workspace_uuid
        return _TenantUow(self._engine)

    def tenant_scope(self, workspace_uuid: str):
        del workspace_uuid
        return _TenantScope()


@pytest.fixture
async def support_admin_api(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "support-admin.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                Workspace.__table__,
                WorkspaceExecutionState.__table__,
                WorkspaceMembership.__table__,
                SupportAdminTemporarySession.__table__,
            ],
        )
        for workspace_uuid, slug in (
            (WORKSPACE_UUID, 'support-admin-a'),
            (OTHER_WORKSPACE_UUID, 'support-admin-b'),
        ):
            await connection.execute(
                sqlalchemy.insert(Workspace).values(
                    uuid=workspace_uuid,
                    instance_uuid=INSTANCE_UUID,
                    name=slug,
                    slug=slug,
                    type='team',
                    status='active',
                    source='cloud_projection',
                    projection_revision=1,
                )
            )
            await connection.execute(
                sqlalchemy.insert(WorkspaceExecutionState).values(
                    workspace_uuid=workspace_uuid,
                    instance_uuid=INSTANCE_UUID,
                    active_generation=1,
                    state='active',
                    write_fenced=False,
                    source='cloud',
                    desired_state_revision=1,
                )
            )

    app = SimpleNamespace()
    app.persistence_mgr = _PersistenceManager(engine)
    app.instance_config = SimpleNamespace(
        data={
            'system': {
                'jwt': {'secret': 'support-admin-secret', 'expire': 3600},
                'websocket_retention': {},
            },
            'space': {
                'launch': {
                    'control_plane_public_key': _base64url(public_key),
                }
            },
            'api': {'global_api_key': ''},
        }
    )
    app.logger = logging.getLogger('support-admin-test')
    app.deployment = SimpleNamespace(mode='cloud', multi_workspace_enabled=True, verification_key_id=KEY_ID)
    app.directory_projection_service = SimpleNamespace(require_ready=lambda: None)
    app.workspace_service = WorkspaceService(app, instance_uuid=INSTANCE_UUID)
    app.entitlement_resolver = SimpleNamespace(
        instance_uuid=INSTANCE_UUID,
        resolve=AsyncMock(return_value=SimpleNamespace(entitlement_revision=7)),
    )
    app.support_admin_session_service = SupportAdminSessionService(app)
    app.space_launch_service = SpaceLaunchService(app)
    app.user_service = SimpleNamespace()
    app.user_service.get_authenticated_account = AsyncMock(side_effect=AssertionError('normal account auth used'))
    app.user_service.verify_jwt_token = AsyncMock(side_effect=AssertionError('normal token verification used'))
    app.user_service.get_user_by_email = AsyncMock(side_effect=AssertionError('user lookup used'))
    app.apikey_service = SimpleNamespace()
    app.apikey_service.authenticate_api_key = AsyncMock(
        return_value=SimpleNamespace(
            instance_uuid=INSTANCE_UUID,
            workspace_uuid=OTHER_WORKSPACE_UUID,
            placement_generation=1,
            api_key_uuid='api-key',
            permissions=frozenset(permission.value for permission in Permission),
        )
    )

    quart_app = Quart(__name__)
    await UserRouterGroup(app, quart_app).initialize()
    await SupportAdminProbeGroup(app, quart_app).initialize()

    yield app, quart_app.test_client(), engine, private_key
    await engine.dispose()


async def _issue_support_token(app, private_key: Ed25519PrivateKey, *, jti: str | None = None) -> dict[str, str]:
    launch = await app.space_launch_service.consume_assertion(
        _sign(private_key, _admin_claims(now=int(time.time()), jti=jti)),
        expected_workspace_uuid=WORKSPACE_UUID,
    )
    return launch


def _auth(token: str, workspace_uuid: str = WORKSPACE_UUID) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}', 'X-Workspace-Id': workspace_uuid}


async def test_support_admin_membership_only_routes_are_denied(support_admin_api):
    app, client, _engine, private_key = support_admin_api
    launch = await _issue_support_token(app, private_key)

    response = await client.get(
        '/api/v1/support-admin-probe/member-operation',
        headers=_auth(launch['support_admin_token']),
    )

    assert response.status_code == 403
    assert (await response.get_json())['code'] == 'permission_denied'


async def test_support_admin_check_token_is_rejected(support_admin_api):
    app, client, _engine, private_key = support_admin_api
    launch = await _issue_support_token(app, private_key)

    response = await client.get('/api/v1/user/check-token', headers=_auth(launch['support_admin_token']))

    assert response.status_code == 401
    assert (await response.get_json())['code'] == 'invalid_authentication'


async def test_support_admin_cross_workspace_denied_for_user_token_and_or_api_key(support_admin_api):
    app, client, _engine, private_key = support_admin_api
    launch = await _issue_support_token(app, private_key)

    missing_selector = await client.get(
        '/api/v1/support-admin-probe/user-token',
        headers={'Authorization': f'Bearer {launch["support_admin_token"]}'},
    )
    user_response = await client.get(
        '/api/v1/support-admin-probe/user-token',
        headers=_auth(launch['support_admin_token'], OTHER_WORKSPACE_UUID),
    )
    either_response = await client.get(
        '/api/v1/support-admin-probe/user-token-or-api-key',
        headers={
            **_auth(launch['support_admin_token'], OTHER_WORKSPACE_UUID),
            'X-API-Key': 'valid-api-key',
        },
    )

    assert missing_selector.status_code == 400
    assert user_response.status_code == 401
    assert either_response.status_code == 401
    app.apikey_service.authenticate_api_key.assert_not_awaited()


async def test_support_admin_request_context_has_actor_owner_and_no_membership(support_admin_api):
    app, client, engine, private_key = support_admin_api
    before_count = await _membership_count(engine)
    launch = await _issue_support_token(app, private_key)

    response = await client.get(
        '/api/v1/support-admin-probe/user-token',
        headers=_auth(launch['support_admin_token']),
    )

    assert response.status_code == 200
    data = (await response.get_json())['data']
    permissions = set(data.pop('permissions'))
    assert Permission.WORKSPACE_VIEW.value in permissions
    assert Permission.RESOURCE_MANAGE.value in permissions
    assert not permissions.intersection(
        {
            Permission.OWNER_TRANSFER.value,
            Permission.MEMBER_VIEW.value,
            Permission.MEMBER_INVITE.value,
            Permission.MEMBER_UPDATE_ROLE.value,
            Permission.MEMBER_REMOVE.value,
        }
    )
    assert data == {
        'principal_type': PrincipalType.SUPPORT_ADMIN.value,
        'actor_account_uuid': ACTOR_ACCOUNT_UUID,
        'account_uuid': None,
        'role': 'owner',
        'membership_uuid': None,
    }
    assert await _membership_count(engine) == before_count


async def test_support_admin_missing_workspace_is_controlled_launch_failure(support_admin_api):
    app, _client, engine, private_key = support_admin_api
    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.delete(WorkspaceExecutionState).where(WorkspaceExecutionState.workspace_uuid == WORKSPACE_UUID)
        )

    with pytest.raises(SpaceLaunchError, match='unavailable'):
        await _issue_support_token(app, private_key)


async def test_support_admin_launch_replay_is_durable_across_service_instances(support_admin_api):
    app, _client, _engine, private_key = support_admin_api
    jti = str(uuid.uuid4())

    await _issue_support_token(app, private_key, jti=jti)
    second_service = SpaceLaunchService(app)

    with pytest.raises(SpaceLaunchError, match='already been consumed'):
        await second_service.consume_assertion(
            _sign(private_key, _admin_claims(now=int(time.time()), jti=jti)),
            expected_workspace_uuid=WORKSPACE_UUID,
        )


async def test_support_admin_persisted_expiry_and_revocation_are_enforced(support_admin_api):
    app, client, engine, private_key = support_admin_api
    launch = await _issue_support_token(app, private_key)
    token = launch['support_admin_token']

    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.update(SupportAdminTemporarySession)
            .where(SupportAdminTemporarySession.grant_jti_hash == launch['grant_jti_hash'])
            .values(expires_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(minutes=1))
        )
    expired = await client.get('/api/v1/support-admin-probe/user-token', headers=_auth(token))
    assert expired.status_code == 401

    second = await _issue_support_token(app, private_key)
    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.update(SupportAdminTemporarySession)
            .where(SupportAdminTemporarySession.grant_jti_hash == second['grant_jti_hash'])
            .values(revoked_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None))
        )
    revoked = await client.get('/api/v1/support-admin-probe/user-token', headers=_auth(second['support_admin_token']))
    assert revoked.status_code == 401


async def test_support_admin_websocket_preserves_actor_and_revalidates(support_admin_api):
    app, _client, _engine, private_key = support_admin_api
    launch = await _issue_support_token(app, private_key)
    captured_contexts = []

    class Adapter:
        async def handle_websocket_message(self, connection, data):
            del data
            captured_contexts.append(connection.execution_context)
            await connection.send_queue.put({'type': 'handled'})
            connection.is_active = False

    app.pipeline_service = SimpleNamespace(get_pipeline=AsyncMock(return_value=SimpleNamespace(uuid='pipeline-1')))
    app.platform_mgr = SimpleNamespace(
        get_websocket_proxy_bot=AsyncMock(return_value=SimpleNamespace(adapter=Adapter()))
    )

    quart_app = Quart(__name__)
    await WebSocketChatRouterGroup(app, quart_app).initialize()

    async with quart_app.test_client().websocket('/api/v1/pipelines/pipeline-1/ws/connect') as websocket:
        await websocket.send(
            json.dumps(
                {
                    'type': 'authenticate',
                    'token': launch['support_admin_token'],
                    'workspace_uuid': WORKSPACE_UUID,
                }
            )
        )
        connected = json.loads(await websocket.receive())
        assert connected['type'] == 'connected'
        await websocket.send(json.dumps({'type': 'message', 'message': [{'type': 'text', 'text': 'hi'}]}))
        handled = json.loads(await websocket.receive())
        assert handled['type'] == 'handled'

    assert captured_contexts
    principal = captured_contexts[0].trigger_principal
    assert principal is not None
    assert principal.principal_type == PrincipalType.SUPPORT_ADMIN
    assert principal.actor_account_uuid == ACTOR_ACCOUNT_UUID


async def _membership_count(engine) -> int:
    async with engine.connect() as connection:
        return int(
            await connection.scalar(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(WorkspaceMembership),
            )
            or 0
        )
