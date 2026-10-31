"""Processor authorization context factory for ApplicationAPI invocation."""

from __future__ import annotations

import typing
import uuid
from collections.abc import Iterable

from ..context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext


async def build_processor_request_context(
    ap: typing.Any,
    *,
    workspace_uuid: str,
    processor_kind: str,
    processor_uuid: str,
    run_id: str,
    operation_ids: Iterable[str],
    trigger_actor: str | None = None,
) -> RequestContext:
    """Build a trusted RequestContext for internal processor invocations."""
    workspace_service = getattr(ap, 'workspace_service', None)
    if workspace_service is None and hasattr(ap, 'ap'):
        workspace_service = getattr(ap.ap, 'workspace_service', None)
    if workspace_service is None:
        raise RuntimeError('Workspace service is required to resolve execution binding')

    binding = await workspace_service.get_execution_binding(workspace_uuid)

    app_api = getattr(ap, 'application_api', None)
    if app_api is None and hasattr(ap, '_operations'):
        app_api = ap
    if app_api is None and hasattr(ap, 'ap'):
        app_api = getattr(ap.ap, 'application_api', None)

    allowed_ids = frozenset(operation_ids)
    permissions: set[str] = set()
    if app_api is not None:
        operations = getattr(app_api, '_operations', {})
        for op_id in allowed_ids:
            spec = operations.get(op_id)
            if spec is not None and getattr(spec, 'permission', None) is not None:
                perm = spec.permission
                permissions.add(perm.value if hasattr(perm, 'value') else str(perm))

    principal = PrincipalContext(
        principal_type=PrincipalType.PROCESSOR,
        account_uuid=None,
        actor_account_uuid=None,
        api_key_uuid=None,
        support_session_id=None,
        processor_kind=processor_kind,
        processor_uuid=processor_uuid,
        run_id=run_id,
        trigger_actor=trigger_actor,
    )
    workspace = WorkspaceContext(
        workspace_uuid=workspace_uuid,
        membership_uuid=None,
        role=None,
        permissions=frozenset(permissions),
        membership_revision=0,
    )
    return RequestContext(
        instance_uuid=binding.instance_uuid,
        placement_generation=binding.placement_generation,
        request_id=str(uuid.uuid4()),
        auth_type='processor',
        principal=principal,
        workspace=workspace,
        entitlement_revision=0,
        allowed_operation_ids=allowed_ids,
    )


__all__ = ['build_processor_request_context']
