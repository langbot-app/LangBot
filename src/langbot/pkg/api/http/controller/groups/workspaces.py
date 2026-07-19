from __future__ import annotations

import typing

import quart

from ...authz import Permission, permissions_for_role
from ...context import RequestContext
from ...service.user import AccountExistsLoginRequiredError, ControlPlaneDirectoryRequiredError
from .....entity.persistence.workspace import Workspace, WorkspaceInvitation, WorkspaceMembership
from .....entity.persistence.workspace import WorkspaceSource
from .....workspace.collaboration import WorkspaceMemberView
from .....workspace.errors import WorkspaceNotFoundError
from .. import group


def _workspace_payload(workspace: Workspace) -> dict[str, typing.Any]:
    return {
        'uuid': workspace.uuid,
        'instance_uuid': workspace.instance_uuid,
        'name': workspace.name,
        'slug': workspace.slug,
        'type': workspace.type,
        'status': workspace.status,
        'source': workspace.source,
    }


def _membership_payload(
    membership: WorkspaceMembership,
    *,
    email: str,
) -> dict[str, typing.Any]:
    return {
        'uuid': membership.uuid,
        'workspace_uuid': membership.workspace_uuid,
        'account_uuid': membership.account_uuid,
        'email': email,
        'role': membership.role,
        'status': membership.status,
        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
        'created_at': membership.created_at.isoformat() if membership.created_at else None,
    }


def _invitation_payload(invitation: WorkspaceInvitation) -> dict[str, typing.Any]:
    """Serialize an invitation without its bearer-secret hash."""

    return {
        'uuid': invitation.uuid,
        'workspace_uuid': invitation.workspace_uuid,
        'normalized_email': invitation.normalized_email,
        'role': invitation.role,
        'status': invitation.status,
        'expires_at': invitation.expires_at.isoformat(),
        'created_at': invitation.created_at.isoformat() if invitation.created_at else None,
    }


@group.group_class('workspaces', '/api/v1/workspaces')
class WorkspacesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/bootstrap', methods=['GET'], auth_type=group.AuthType.ACCOUNT_TOKEN)
        async def _(user_email: str) -> typing.Any:
            """List the active Workspaces available to an authenticated Account.

            This account-only endpoint intentionally runs before Workspace
            selection. It never accepts a selector as authority and does not
            choose a default Workspace for a multi-membership Account.
            """

            account = await self.ap.user_service.get_user_by_email(user_email)
            if account is None:
                return self.http_status(401, 'invalid_authentication', 'Account not found')
            accesses = await self.ap.workspace_collaboration_service.list_account_workspaces(account.uuid)
            return self.success(
                data={
                    'workspaces': [
                        {
                            'workspace': _workspace_payload(access.workspace),
                            'membership': _membership_payload(access.membership, email=account.user),
                            'permissions': sorted(permissions_for_role(access.membership.role)),
                            'placement_generation': access.execution.placement_generation,
                        }
                        for access in accesses
                    ]
                }
            )

        @self.route('', methods=['GET', 'POST'], permission=Permission.WORKSPACE_VIEW)
        async def _(request_context: RequestContext) -> typing.Any:
            if quart.request.method == 'POST':
                if self.ap.workspace_service.policy.multi_workspace_enabled:
                    return self.http_status(
                        409,
                        'control_plane_required',
                        'Cloud Workspaces are created by the SaaS control plane',
                    )
                return self.http_status(403, 'edition_limit', 'This edition supports one Workspace per instance')

            accesses = await self.ap.workspace_collaboration_service.list_account_workspaces(
                request_context.account_uuid
            )
            return self.success(data={'workspaces': [_workspace_payload(access.workspace) for access in accesses]})

        @self.route('/current', methods=['GET'], permission=Permission.WORKSPACE_VIEW)
        async def _(request_context: RequestContext) -> typing.Any:
            membership = quart.g.workspace_membership
            account = await self.ap.user_service.get_user_by_uuid(request_context.account_uuid)
            if account is None:
                return self.http_status(401, 'invalid_authentication', 'Account not found')
            workspace = await self.ap.workspace_service.get_workspace(request_context.workspace_uuid)
            return self.success(
                data={
                    'workspace': _workspace_payload(workspace),
                    'membership': _membership_payload(membership, email=account.user),
                    'permissions': sorted(request_context.workspace.permissions),
                    'placement_generation': request_context.placement_generation,
                }
            )

        @self.route('/<workspace_uuid>', methods=['GET'], permission=Permission.WORKSPACE_VIEW)
        async def _(workspace_uuid: str, request_context: RequestContext) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            workspace = await self.ap.workspace_service.get_workspace(workspace_uuid)
            return self.success(data={'workspace': _workspace_payload(workspace)})

        @self.route('/<workspace_uuid>/members', methods=['GET'], permission=Permission.MEMBER_VIEW)
        async def _(workspace_uuid: str, request_context: RequestContext) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            members = await self.ap.workspace_collaboration_service.list_members(
                workspace_uuid,
                quart.g.workspace_membership,
            )
            return self.success(data={'members': [self._member_view_payload(item) for item in members]})

        @self.route(
            '/<workspace_uuid>/invitations',
            methods=['GET', 'POST'],
            permission=Permission.MEMBER_INVITE,
        )
        async def _(workspace_uuid: str, request_context: RequestContext) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            if await self._requires_control_plane(workspace_uuid):
                return self._control_plane_required()
            if quart.request.method == 'GET':
                invitations = await self.ap.workspace_collaboration_service.list_invitations(
                    workspace_uuid,
                    quart.g.workspace_membership,
                )
                return self.success(data={'invitations': [_invitation_payload(item) for item in invitations]})

            data = await quart.request.get_json(silent=True) or {}
            created = await self.ap.workspace_collaboration_service.create_invitation(
                workspace_uuid,
                quart.g.workspace_membership,
                str(data.get('email', '')),
                str(data.get('role', 'viewer')),
            )
            return self.success(
                data={
                    'invitation': _invitation_payload(created.invitation),
                    'token': created.token,
                }
            )

        @self.route(
            '/<workspace_uuid>/invitations/<invitation_uuid>',
            methods=['DELETE'],
            permission=Permission.MEMBER_INVITE,
        )
        async def _(
            workspace_uuid: str,
            invitation_uuid: str,
            request_context: RequestContext,
        ) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            if await self._requires_control_plane(workspace_uuid):
                return self._control_plane_required()
            invitation = await self.ap.workspace_collaboration_service.revoke_invitation(
                workspace_uuid,
                invitation_uuid,
                quart.g.workspace_membership,
            )
            return self.success(data={'invitation': _invitation_payload(invitation)})

        @self.route(
            '/<workspace_uuid>/members/<account_uuid>',
            methods=['PATCH', 'DELETE'],
            permission=Permission.MEMBER_UPDATE_ROLE,
        )
        async def _(
            workspace_uuid: str,
            account_uuid: str,
            request_context: RequestContext,
        ) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            if await self._requires_control_plane(workspace_uuid):
                return self._control_plane_required()
            if quart.request.method == 'DELETE':
                if Permission.MEMBER_REMOVE.value not in request_context.workspace.permissions:
                    return self.http_status(403, 'permission_denied', 'Member removal permission is required')
                member = await self.ap.workspace_collaboration_service.remove_member(
                    workspace_uuid,
                    account_uuid,
                    quart.g.workspace_membership,
                )
                return self.success(data={'account_uuid': member.account_uuid})

            data = await quart.request.get_json(silent=True) or {}
            member = await self.ap.workspace_collaboration_service.update_member_role(
                workspace_uuid,
                account_uuid,
                str(data.get('role', '')),
                quart.g.workspace_membership,
            )
            account = await self.ap.user_service.get_user_by_uuid(member.account_uuid)
            return self.success(
                data={
                    'member': _membership_payload(
                        member,
                        email=account.user if account is not None else '',
                    )
                }
            )

    @staticmethod
    def _require_current_workspace(workspace_uuid: str, request_context: RequestContext) -> None:
        if workspace_uuid != request_context.workspace_uuid:
            raise WorkspaceNotFoundError('Workspace not found')

    async def _requires_control_plane(self, workspace_uuid: str) -> bool:
        workspace = await self.ap.workspace_service.get_workspace(workspace_uuid)
        return workspace.source == WorkspaceSource.CLOUD_PROJECTION.value

    def _control_plane_required(self) -> typing.Any:
        return self.http_status(
            409,
            'control_plane_required',
            'Cloud Workspace membership and invitations are managed by the SaaS control plane',
        )

    @staticmethod
    def _member_view_payload(view: WorkspaceMemberView) -> dict[str, typing.Any]:
        return _membership_payload(view.membership, email=view.email)


@group.group_class('invitations', '/api/v1/invitations')
class InvitationsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/inspect', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> typing.Any:
            data = await quart.request.get_json(silent=True) or {}
            invitation, workspace = await self.ap.workspace_collaboration_service.inspect_invitation(
                str(data.get('token', ''))
            )
            return self.success(
                data={
                    'invitation': _invitation_payload(invitation),
                    'workspace': _workspace_payload(workspace),
                }
            )

        @self.route('/accept', methods=['POST'], auth_type=group.AuthType.NONE)
        async def _() -> typing.Any:
            data = await quart.request.get_json(silent=True) or {}
            invitation_token = str(data.get('token', ''))
            if not invitation_token:
                return self.http_status(400, 'invitation_invalid', 'Invitation token is required')

            authorization = quart.request.headers.get('Authorization', '')
            if authorization.startswith('Bearer '):
                account = await self.ap.user_service.get_authenticated_account(authorization.removeprefix('Bearer '))
                if isinstance(account, str):
                    account = await self.ap.user_service.get_user_by_email(account)
                if account is None:
                    return self.http_status(401, 'invalid_authentication', 'Account not found')
                membership = await self.ap.workspace_collaboration_service.accept_invitation(
                    invitation_token,
                    account.uuid,
                )
                token = await self.ap.user_service.generate_jwt_token(account)
                return self.success(data={'token': token, 'workspace_uuid': membership.workspace_uuid})

            registration = data.get('registration')
            if not isinstance(registration, dict):
                return self.http_status(
                    401,
                    'account_exists_login_required',
                    'Sign in or provide registration details to accept this invitation',
                )
            password = registration.get('password')
            if not isinstance(password, str) or len(password) < 8:
                return self.http_status(400, 'invalid_password', 'Password must contain at least 8 characters')
            try:
                _, membership, token = await self.ap.user_service.register_invited_account(
                    invitation_token,
                    str(registration.get('email', '')),
                    password,
                )
            except ControlPlaneDirectoryRequiredError as exc:
                return self.http_status(409, exc.code, str(exc))
            except AccountExistsLoginRequiredError as exc:
                return self.http_status(409, exc.code, str(exc))
            return self.success(data={'token': token, 'workspace_uuid': membership.workspace_uuid})
