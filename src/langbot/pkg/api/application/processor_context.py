"""Processor authorization context factory for ApplicationAPI invocation."""

from __future__ import annotations

import typing
import uuid
from collections.abc import Iterable

from ..context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext

_VALID_PROCESSOR_KINDS: typing.Final = frozenset({'agent', 'pipeline', 'event_processor'})


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
    if not isinstance(workspace_uuid, str) or not workspace_uuid.strip():
        raise ValueError('workspace_uuid is required')
    if processor_kind not in _VALID_PROCESSOR_KINDS:
        raise ValueError(f'Invalid processor_kind {processor_kind!r}; must be one of {sorted(_VALID_PROCESSOR_KINDS)}')
    if not isinstance(processor_uuid, str) or not processor_uuid.strip():
        raise ValueError('processor_uuid is required')
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError('run_id is required')

    binding = await ap.workspace_service.get_execution_binding(workspace_uuid)

    allowed_ids = frozenset(operation_ids)
    permissions: set[str] = set()
    app_api = getattr(ap, 'application_api', None)
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
