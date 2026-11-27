"""Account authentication inside an established HTS1 channel."""

import asyncio
import hmac
import uuid

import jwt
import sqlalchemy as sa

from ..api.authz import permissions_for_role
from ..api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from ..entity.persistence.harness_oauth import HarnessDevice, HarnessOAuthGrant
from ..entity.persistence.harness_registration import HarnessBinding
from ..utils import constants
from .oauth import SCOPE_PERMISSIONS


async def _oauth_context(
    ap, token: str, workspace_uuid: str | None = None, *, device_id: str | None = None, binding_id: str | None = None,
):
    """Resolve a Harness access token against live grant, device and membership records."""
    try:
        claims = jwt.decode(
            token,
            ap.instance_config.data['system']['jwt']['secret'],
            algorithms=['HS256'],
            issuer=constants.instance_id,
            options={'require': ['exp', 'iat', 'iss', 'sub', 'ws', 'bid', 'dev', 'gid', 'scp']},
        )
    except Exception as exc:
        raise ValueError('invalid_harness_access_token') from exc
    if claims.get('typ') != 'langbot_harness_at':
        raise ValueError('invalid_harness_access_token')
    if (device_id is not None and claims['dev'] != device_id) or (
        binding_id is not None and claims['bid'] != binding_id
    ):
        raise ValueError('invalid_harness_access_token')
    if workspace_uuid is not None and workspace_uuid != claims['ws']:
        raise ValueError('workspace_forbidden')
    scopes = claims['scp'] if isinstance(claims['scp'], list) else []
    async with ap.persistence_mgr.get_db_engine().connect() as conn:
        row = (
            (
                await conn.execute(
                    sa.select(HarnessOAuthGrant.__table__)
                    .join(HarnessBinding, HarnessBinding.id == HarnessOAuthGrant.binding_id)
                    .join(HarnessDevice, HarnessDevice.id == HarnessOAuthGrant.device_id)
                    .where(
                        HarnessOAuthGrant.id == claims['gid'],
                        HarnessOAuthGrant.account_uuid == claims['sub'],
                        HarnessOAuthGrant.workspace_uuid == claims['ws'],
                        HarnessOAuthGrant.binding_id == claims['bid'],
                        HarnessOAuthGrant.device_id == claims['dev'],
                        HarnessOAuthGrant.revoked_at.is_(None),
                        HarnessBinding.instance_uuid == constants.instance_id,
                        HarnessBinding.revoked_at.is_(None),
                        HarnessDevice.revoked_at.is_(None),
                        HarnessDevice.account_uuid == claims['sub'],
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise ValueError('invalid_harness_grant')
    account = await ap.user_service.get_user_by_uuid(claims['sub'])
    if account is None or account.status != 'active':
        raise ValueError('account_not_found')
    access = await ap.workspace_collaboration_service.resolve_account_workspace(account.uuid, claims['ws'])
    role_permissions = set(permissions_for_role(access.membership.role))
    effective = frozenset(
        SCOPE_PERMISSIONS[scope]
        for scope in scopes
        if scope in SCOPE_PERMISSIONS and SCOPE_PERMISSIONS[scope] in role_permissions
    )
    if not effective:
        raise ValueError('insufficient_scope')
    context = RequestContext(
        instance_uuid=constants.instance_id,
        placement_generation=access.execution.placement_generation,
        request_id=str(uuid.uuid4()),
        auth_type='harness-oauth',
        harness_device_id=claims['dev'],
        principal=PrincipalContext(principal_type=PrincipalType.ACCOUNT, account_uuid=account.uuid),
        workspace=WorkspaceContext(
            workspace_uuid=access.workspace.uuid,
            membership_uuid=access.membership.uuid,
            role=access.membership.role,
            permissions=effective,
            membership_revision=access.membership.projection_revision,
        ),
    )

    async def revalidate(message):
        current, _ = await _oauth_context(ap, token, context.workspace_uuid)
        return current

    return context, revalidate


async def authenticate_session(ap, session):
    """Authenticate an existing instance account token and resolve its Workspace."""
    async with asyncio.timeout(15):
        payload = await session.receive_payload()
        if not isinstance(payload, dict) or payload.get('type') != 'authenticate':
            raise ValueError('Harness account authentication is required')
        auth = payload.get('auth')
        workspace_uuid = payload.get('workspace_uuid')
        if (
            not isinstance(auth, dict)
            or auth.get('kind') not in {'user_token', 'oauth'}
            or not isinstance(auth.get('token'), str)
            or not 0 < len(auth['token']) <= 8192
            or not isinstance(workspace_uuid, str)
            or not 0 < len(workspace_uuid) <= 36
        ):
            raise ValueError('Invalid Harness authentication request')
        token = auth['token']
        if auth.get('kind') == 'oauth':
            return await _oauth_context(ap, token, workspace_uuid)
        if ap.instance_config.data.get('harness', {}).get('enabled') is True:
            raise ValueError('Harness OAuth authentication is required')
        account = await ap.user_service.get_authenticated_account(token)
        access = await ap.workspace_collaboration_service.resolve_account_workspace(account.uuid, workspace_uuid)
        context = RequestContext(
            instance_uuid=access.execution.instance_uuid,
            placement_generation=access.execution.placement_generation,
            request_id=str(uuid.uuid4()),
            auth_type='user-token',
            principal=PrincipalContext(principal_type=PrincipalType.ACCOUNT, account_uuid=account.uuid),
            workspace=WorkspaceContext(
                workspace_uuid=access.workspace.uuid,
                membership_uuid=access.membership.uuid,
                role=access.membership.role,
                permissions=permissions_for_role(access.membership.role),
                membership_revision=access.membership.projection_revision,
            ),
        )

    async def revalidate(message):
        current = await ap.user_service.get_authenticated_account(token)
        if current.uuid != context.account_uuid:
            raise ValueError('Harness authenticated account changed')
        current_access = await ap.workspace_collaboration_service.resolve_account_workspace(
            context.account_uuid, context.workspace_uuid
        )
        if (
            current_access.execution.instance_uuid != context.instance_uuid
            or current_access.execution.placement_generation != context.placement_generation
            or current_access.membership.uuid != context.workspace.membership_uuid
            or current_access.membership.projection_revision != context.workspace.membership_revision
        ):
            raise ValueError('Harness Workspace authorization changed')
        csrf = message.get('csrf_token') if isinstance(message, dict) else None
        if not isinstance(csrf, str) or not hmac.compare_digest(csrf, session.authenticated_csrf):
            raise ValueError('Harness session proof is invalid')

    import secrets

    session.authenticated_csrf = secrets.token_urlsafe(24)
    await session.send_payload(
        {
            'type': 'authenticated',
            'account_uuid': context.account_uuid,
            'workspace_uuid': context.workspace_uuid,
            'csrf_token': session.authenticated_csrf,
        }
    )

    return context, revalidate
