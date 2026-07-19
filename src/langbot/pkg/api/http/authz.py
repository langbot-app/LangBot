from __future__ import annotations

import enum
import types
import typing

from .context import RequestContext


class WorkspaceRole(enum.StrEnum):
    OWNER = 'owner'
    ADMIN = 'admin'
    DEVELOPER = 'developer'
    OPERATOR = 'operator'
    VIEWER = 'viewer'


class Permission(enum.StrEnum):
    WORKSPACE_VIEW = 'workspace.view'
    WORKSPACE_UPDATE = 'workspace.update'
    WORKSPACE_DELETE = 'workspace.delete'
    OWNER_TRANSFER = 'owner.transfer'
    MEMBER_VIEW = 'member.view'
    MEMBER_INVITE = 'member.invite'
    MEMBER_UPDATE_ROLE = 'member.update_role'
    MEMBER_REMOVE = 'member.remove'
    RESOURCE_VIEW = 'resource.view'
    RESOURCE_MANAGE = 'resource.manage'
    RUNTIME_OPERATE = 'runtime.operate'
    PROVIDER_SECRET_MANAGE = 'provider_secret.manage'
    API_KEY_MANAGE = 'api_key.manage'
    AUDIT_VIEW = 'audit.view'
    DATA_EXPORT = 'data.export'
    BILLING_LINK_MANAGE = 'billing_link.manage'


_VIEW_PERMISSIONS = {
    Permission.WORKSPACE_VIEW,
    Permission.MEMBER_VIEW,
    Permission.RESOURCE_VIEW,
}

_ROLE_PERMISSIONS: typing.Final = types.MappingProxyType(
    {
        WorkspaceRole.OWNER: frozenset(Permission),
        WorkspaceRole.ADMIN: frozenset(
            permission
            for permission in Permission
            if permission
            not in {
                Permission.WORKSPACE_DELETE,
                Permission.OWNER_TRANSFER,
                Permission.BILLING_LINK_MANAGE,
            }
        ),
        WorkspaceRole.DEVELOPER: frozenset(
            _VIEW_PERMISSIONS
            | {
                Permission.RESOURCE_MANAGE,
                Permission.RUNTIME_OPERATE,
                Permission.PROVIDER_SECRET_MANAGE,
            }
        ),
        WorkspaceRole.OPERATOR: frozenset(_VIEW_PERMISSIONS | {Permission.RUNTIME_OPERATE}),
        WorkspaceRole.VIEWER: frozenset(_VIEW_PERMISSIONS),
    }
)


class AuthorizationError(Exception):
    """Base class for errors that map to an HTTP authorization response."""

    status_code = 403
    error_code = 'forbidden'


class WorkspaceRequiredError(AuthorizationError):
    status_code = 400
    error_code = 'workspace_required'


class PermissionDeniedError(AuthorizationError):
    error_code = 'permission_denied'

    def __init__(self, permission: str) -> None:
        super().__init__(f'Missing Workspace permission: {permission}')
        self.permission = permission


class EditionLimitError(AuthorizationError):
    error_code = 'edition_limit'


def permissions_for_role(role: str | WorkspaceRole) -> frozenset[str]:
    """Return the canonical fixed permissions for a Workspace role."""

    try:
        parsed_role = WorkspaceRole(role)
    except ValueError:
        return frozenset()
    return frozenset(permission.value for permission in _ROLE_PERMISSIONS[parsed_role])


def has_permission(ctx: RequestContext, permission: str | Permission) -> bool:
    """Return whether the context contains one effective permission."""

    permission_value = permission.value if isinstance(permission, Permission) else permission
    return permission_value in ctx.workspace.permissions


def require_permission(ctx: RequestContext, permission: str | Permission) -> None:
    """Raise a stable authorization error when a permission is missing."""

    permission_value = permission.value if isinstance(permission, Permission) else permission
    if not has_permission(ctx, permission_value):
        raise PermissionDeniedError(permission_value)
