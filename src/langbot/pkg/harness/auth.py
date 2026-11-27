"""Account authentication inside an established HTS1 channel."""

import asyncio
import hmac
import uuid

from ..api.authz import permissions_for_role
from ..api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext


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
            or auth.get('kind') != 'user_token'
            or not isinstance(auth.get('token'), str)
            or not 0 < len(auth['token']) <= 8192
            or not isinstance(workspace_uuid, str)
            or not 0 < len(workspace_uuid) <= 36
        ):
            raise ValueError('Invalid Harness authentication request')
        token = auth['token']
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
