from __future__ import annotations

import typing

from ..authz import WorkspaceRequiredError
from ..context import ExecutionContext, RequestContext, WorkspaceContext

TenantContext: typing.TypeAlias = RequestContext | ExecutionContext | WorkspaceContext | str


def require_workspace_uuid(context: TenantContext | None) -> str:
    """Resolve an explicit Workspace UUID without allowing a global fallback."""

    if isinstance(context, str):
        workspace_uuid = context
    elif isinstance(context, RequestContext):
        workspace_uuid = context.workspace_uuid
    elif isinstance(context, ExecutionContext):
        workspace_uuid = context.workspace_uuid
    elif isinstance(context, WorkspaceContext):
        workspace_uuid = context.workspace_uuid
    else:
        raise WorkspaceRequiredError('Workspace context is required')

    normalized = workspace_uuid.strip()
    if not normalized:
        raise WorkspaceRequiredError('Workspace context is required')
    return normalized


def scope_statement(statement: typing.Any, model: typing.Any, context: TenantContext) -> typing.Any:
    """Add the mandatory Workspace predicate to a SQLAlchemy statement."""

    return statement.where(model.workspace_uuid == require_workspace_uuid(context))
