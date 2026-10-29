from __future__ import annotations

import typing

import quart

from ...authz import Permission, permissions_for_role
from ...context import RequestContext
from ...service.user import AccountExistsLoginRequiredError, ControlPlaneDirectoryRequiredError
from .....entity.persistence.workspace import Workspace, WorkspaceInvitation, WorkspaceMembership
from .....entity.persistence.workspace import WorkspaceSource
from .....workspace.errors import WorkspaceNotFoundError
from .....operation_trace import service as settings_service
from .. import group
from .....i18n import SUPPORTED_LANGUAGES


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
    display_name: str,
    email: str,
) -> dict[str, typing.Any]:
    return {
        'uuid': membership.uuid,
        'workspace_uuid': membership.workspace_uuid,
        'account_uuid': membership.account_uuid,
        'display_name': display_name,
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
        @self.route(
            '/current/language',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.WORKSPACE_VIEW,
        )
        async def get_language(request_context: RequestContext):
            return self.success(data=await self.call_application('workspace.language.get', request_context, {}))

        @self.route(
            '/current/language',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.WORKSPACE_UPDATE,
        )
        async def update_language(request_context: RequestContext):
            body = await quart.request.get_json()
            locale = body.get('language') if isinstance(body, dict) else None
            if locale not in SUPPORTED_LANGUAGES:
                return self.http_status(400, 'invalid_language', 'Unsupported Workspace language')
            return self.success(
                data=await self.call_application('workspace.language.update', request_context, {'language': locale})
            )

        @self.route('/bootstrap', methods=['GET'], auth_type=group.AuthType.ACCOUNT_TOKEN)
        async def _(account) -> typing.Any:
            """List the active Workspaces available to an authenticated Account.

            This account-only endpoint intentionally runs before Workspace
            selection. It never accepts a selector as authority and does not
            choose a default Workspace for a multi-membership Account.
            """

            accesses = await self.ap.workspace_collaboration_service.list_account_workspaces(account.uuid)
            resolver = getattr(self.ap, 'entitlement_resolver', None)
            workspaces: list[dict[str, typing.Any]] = []
            for access in accesses:
                plan_name: str | None = None
                if access.workspace.source == WorkspaceSource.CLOUD_PROJECTION.value and resolver is not None:
                    entitlement = await resolver.resolve(
                        access.workspace.uuid,
                        minimum_revision=access.membership.projection_revision,
                    )
                    plan_name = entitlement.plan_name
                workspaces.append(
                    {
                        'workspace': _workspace_payload(access.workspace),
                        'membership': _membership_payload(
                            access.membership,
                            display_name=account.user,
                            email=account.normalized_email,
                        ),
                        'permissions': sorted(permissions_for_role(access.membership.role)),
                        'placement_generation': access.execution.placement_generation,
                        'plan_name': plan_name,
                    }
                )
            return self.success(data={'workspaces': workspaces})

        @self.route('', methods=['GET'], auth_type=group.AuthType.ACCOUNT_TOKEN)
        async def _(account) -> typing.Any:
            accesses = await self.ap.workspace_collaboration_service.list_account_workspaces(account.uuid)
            return self.success(data={'workspaces': [_workspace_payload(access.workspace) for access in accesses]})

        @self.route('', methods=['POST'], permission=Permission.WORKSPACE_VIEW)
        async def _(request_context: RequestContext) -> typing.Any:
            if self.ap.workspace_service.policy.multi_workspace_enabled:
                return self.http_status(
                    409,
                    'control_plane_required',
                    'Cloud Workspaces are created by the SaaS control plane',
                )
            return self.http_status(403, 'edition_limit', 'This edition supports one Workspace per instance')

        @self.route('/current', methods=['GET'], permission=Permission.WORKSPACE_VIEW)
        async def _(request_context: RequestContext) -> typing.Any:
            return self.success(data=await self.call_application('workspace.current', request_context, {}))

        @self.route('/<workspace_uuid>', methods=['GET'], permission=Permission.WORKSPACE_VIEW)
        async def _(workspace_uuid: str, request_context: RequestContext) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            workspace = await self.call_application('workspace.get', request_context, {})
            return self.success(data={'workspace': workspace})

        @self.route('/<workspace_uuid>/members', methods=['GET'], permission=Permission.MEMBER_VIEW)
        async def _(workspace_uuid: str, request_context: RequestContext) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            members = await self.call_application('workspace.member.list', request_context, {})
            return self.success(data={'members': members})

        @self.route(
            '/<workspace_uuid>/invitations',
            methods=['GET', 'POST'],
            permission=Permission.MEMBER_INVITE,
        )
        async def _(workspace_uuid: str, request_context: RequestContext) -> typing.Any:
            self._require_current_workspace(workspace_uuid, request_context)
            if quart.request.method == 'GET':
                invitations = await self.call_application('workspace.invitation.list', request_context, {})
                return self.success(data={'invitations': invitations})
            data = await quart.request.get_json(silent=True) or {}
            created = await self.call_application(
                'workspace.invitation.create',
                request_context,
                {
                    'email': str(data.get('email', '')),
                    'role': str(data.get('role', 'viewer')),
                },
            )
            invitation = created['invitation']
            invite_rule = settings_service.ACTION_RULES_BY_ACTION['member_invite']
            invite_changes = [
                {
                    'field': 'invitation',
                    'before': None,
                    'after': f'{invitation["normalized_email"]}:{invitation["role"]}',
                }
            ]
            quart.g.operation_log_changes = invite_changes
            quart.g.operation_log_resource_id = invitation['uuid']
            quart.g.operation_log_detail = {'role': invitation['role']}
            quart.g.operation_log_summary = settings_service.build_summary(invite_rule, invite_changes)
            return self.success(data=created)

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
            invitation = await self.call_application(
                'workspace.invitation.revoke', request_context, {'invitation_uuid': invitation_uuid}
            )
            return self.success(data={'invitation': invitation})

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
            before_role = await self._member_role(request_context, account_uuid)
            if quart.request.method == 'DELETE':
                if Permission.MEMBER_REMOVE.value not in request_context.workspace.permissions:
                    return self.http_status(403, 'permission_denied', 'Member removal permission is required')
                member = await self.call_application(
                    'workspace.member.remove', request_context, {'account_uuid': account_uuid}
                )
                await self._publish_member_trace(
                    rule_action='member_remove',
                    account_uuid=account_uuid,
                    changes=[
                        {'field': 'member', 'before': f'{account_uuid}:{before_role or "unknown"}', 'after': 'removed'}
                    ],
                )
                return self.success(data=member)
            data = await quart.request.get_json(silent=True) or {}
            member = await self.call_application(
                'workspace.member.update',
                request_context,
                {
                    'account_uuid': account_uuid,
                    'role': str(data.get('role', '')),
                },
            )
            await self._publish_member_trace(
                rule_action='member_role_update',
                account_uuid=account_uuid,
                changes=[{'field': 'role', 'before': before_role, 'after': member['role']}],
                detail={'member_email': member['email'] or None},
            )
            return self.success(data={'member': member})

    async def _member_role(self, request_context: RequestContext, account_uuid: str) -> str | None:
        """Return a member's current role without failing the request."""

        try:
            members = await self.call_application('workspace.member.list', request_context, {})
        except Exception:
            return None
        for view in members:
            if view['account_uuid'] == account_uuid:
                return view['role']
        return None

    async def _publish_member_trace(
        self,
        *,
        rule_action: str,
        account_uuid: str,
        changes: list[dict[str, typing.Any]],
        detail: dict[str, typing.Any] | None = None,
    ) -> None:
        """Publish request-local trace facts consumed by the route wrapper.

        ``quart.g`` is request-local, so concurrent member operations never
        share these values.
        """

        rule = settings_service.ACTION_RULES_BY_ACTION.get(rule_action)
        quart.g.operation_log_changes = changes
        quart.g.operation_log_resource_id = account_uuid
        quart.g.operation_log_detail = detail or {}
        if rule is not None:
            quart.g.operation_log_summary = settings_service.build_summary(rule, changes)

    @staticmethod
    def _require_current_workspace(workspace_uuid: str, request_context: RequestContext) -> None:
        if workspace_uuid != request_context.workspace_uuid:
            raise WorkspaceNotFoundError('Workspace not found')


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
                if getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') != 'cloud':
                    return self.http_status(
                        409,
                        'invitation_logout_required',
                        'Sign out before creating the invited local Account',
                    )
                try:
                    account = await self.ap.user_service.get_authenticated_account(
                        authorization.removeprefix('Bearer ')
                    )
                    if isinstance(account, str):
                        account = await self.ap.user_service.get_user_by_email(account)
                except Exception as exc:
                    return self._auth_error_response(exc)
                if account is None:
                    return self.http_status(401, 'invalid_authentication', 'Account not found')
                membership = await self.ap.workspace_collaboration_service.accept_invitation(
                    invitation_token,
                    account.uuid,
                )
                token = await self.ap.user_service.generate_jwt_token(account)
                return self.success(data={'token': token, 'workspace_uuid': membership.workspace_uuid})

            registration = data.get('registration')
            if getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud':
                return self.http_status(
                    401,
                    'account_exists_login_required',
                    'Login with your LangBot Account to accept this invitation',
                )
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
                _, membership = await self.ap.user_service.register_invited_account(
                    invitation_token,
                    str(registration.get('email', '')),
                    password,
                )
            except ControlPlaneDirectoryRequiredError as exc:
                return self.http_status(409, exc.code, str(exc))
            except AccountExistsLoginRequiredError as exc:
                return self.http_status(409, exc.code, str(exc))
            return self.success(data={'workspace_uuid': membership.workspace_uuid, 'login_required': True})
