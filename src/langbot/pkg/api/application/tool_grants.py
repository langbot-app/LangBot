"""Processor workspace operations authorization and catalog."""

from __future__ import annotations

from typing import Any, Iterable

from ..authz import has_permission
from ..context import PrincipalType, RequestContext
from .contracts import ApplicationAPIError, ApplicationAPIException, Operation
from .operation_docs import DOMAINS, get_operation_doc


def _is_processor(context: Any) -> bool:
    principal = getattr(context, 'principal', None)
    return getattr(principal, 'principal_type', None) == PrincipalType.PROCESSOR


def validate_grant_change(
    ap: Any,
    editor_context: RequestContext,
    old_ids: Iterable[str] | None,
    new_ids: Iterable[str] | None,
) -> list[str]:
    """Validate additions to granted workspace operations for a processor.

    Existing grants are preserved without re-validation so low-privileged members
    can update other processor fields without losing existing high-privilege grants.
    Removals are unrestricted.
    """
    if new_ids is None:
        new_ids = []
    if old_ids is None:
        old_ids = []

    if not isinstance(new_ids, (list, tuple, set, frozenset)):
        raise ApplicationAPIException(
            ApplicationAPIError(
                code='invalid_input',
                message='Workspace operations must be a list of strings',
                status_code=400,
                details={'operations': []},
            )
        )

    for item in new_ids:
        if not isinstance(item, str):
            raise ApplicationAPIException(
                ApplicationAPIError(
                    code='invalid_input',
                    message='Workspace operation IDs must be strings',
                    status_code=400,
                    details={'operations': [item]},
                )
            )

    for item in old_ids:
        if not isinstance(item, str):
            raise ApplicationAPIException(
                ApplicationAPIError(
                    code='invalid_input',
                    message='Workspace operation IDs must be strings',
                    status_code=400,
                    details={'operations': [item]},
                )
            )

    normalized_new = sorted(set(new_ids))
    normalized_old = set(old_ids)
    added_ids = [op for op in normalized_new if op not in normalized_old]

    if not added_ids:
        return normalized_new

    # Granting is a human authorization act. A processor that can update processor
    # configuration must not widen any processor's grants, including its own.
    if _is_processor(editor_context):
        raise ApplicationAPIException(
            ApplicationAPIError(
                code='permission_denied',
                message=f'Processors cannot grant workspace operations: {added_ids}',
                status_code=403,
                details={'operations': added_ids, 'denied_operations': added_ids},
            )
        )

    app_api = getattr(ap, 'application_api', None)
    if app_api is None:
        from .api import ApplicationAPI

        app_api = ApplicationAPI(ap)

    operations_map: dict[str, Operation] = getattr(app_api, '_operations', {})

    invalid_ids: list[str] = []
    denied_ids: list[str] = []

    for op_id in added_ids:
        spec = operations_map.get(op_id)
        if spec is None:
            invalid_ids.append(op_id)
            continue

        if spec.streaming:
            invalid_ids.append(op_id)
            continue

        if spec.principals is not None and PrincipalType.PROCESSOR not in spec.principals:
            invalid_ids.append(op_id)
            continue

        doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
        if doc.exposure != 'all':
            invalid_ids.append(op_id)
            continue

        if (
            editor_context is None
            or not hasattr(editor_context, 'workspace')
            or not has_permission(editor_context, spec.permission)
        ):
            denied_ids.append(op_id)

    if invalid_ids:
        raise ApplicationAPIException(
            ApplicationAPIError(
                code='invalid_input',
                message=f'Invalid workspace operations: {invalid_ids}',
                status_code=400,
                details={'operations': invalid_ids, 'invalid_operations': invalid_ids},
            )
        )

    if denied_ids:
        raise ApplicationAPIException(
            ApplicationAPIError(
                code='permission_denied',
                message=f'Permission denied for workspace operations: {denied_ids}',
                status_code=403,
                details={'operations': denied_ids, 'denied_operations': denied_ids},
            )
        )

    return normalized_new


def get_workspace_operations_catalog(ap: Any, context: Any) -> dict[str, Any]:
    """Return the operations catalog and domains metadata for processor tool granting."""
    app_api = getattr(ap, 'application_api', None)
    if app_api is None:
        from .api import ApplicationAPI

        app_api = ApplicationAPI(ap)

    operations_map: dict[str, Operation] = getattr(app_api, '_operations', {})
    ops: list[dict[str, Any]] = []
    seen_domains: set[str] = set()

    for _op_id, spec in sorted(operations_map.items()):
        doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
        if doc.exposure != 'all':
            continue

        can_run = (not spec.streaming) and (spec.principals is None or PrincipalType.PROCESSOR in spec.principals)
        has_perm = (
            has_permission(context, spec.permission) if context is not None and hasattr(context, 'workspace') else False
        )
        grantable = bool(can_run and has_perm and not _is_processor(context))

        perm = spec.permission
        perm_str = perm.value if hasattr(perm, 'value') else str(perm)

        ops.append(
            {
                'id': spec.operation_id,
                'domain': doc.domain,
                'label': doc.label,
                'summary': doc.summary,
                'risk': doc.risk,
                'permission': perm_str,
                'grantable': grantable,
            }
        )
        seen_domains.add(doc.domain)

    domains_list = [
        {
            'domain': d,
            'label': DOMAINS.get(d, {}).get('label', {'zh_Hans': d, 'en_US': d.capitalize()}),
            'summary': DOMAINS.get(d, {}).get('summary', ''),
        }
        for d in sorted(seen_domains)
    ]

    return {
        'workspace_operations': ops,
        'domains': domains_list,
    }


def get_default_workspace_operations(ap: Any, declared_operations: Iterable[str] | None) -> list[str]:
    """Calculate default workspace operations from runner declared operations.

    Default scope is declared_workspace_operations intersected with catalog operations
    where exposure == 'all', non-streaming, and processor principal is allowed.
    """
    if not declared_operations:
        return []

    app_api = getattr(ap, 'application_api', None)
    if app_api is None:
        from .api import ApplicationAPI

        app_api = ApplicationAPI(ap)

    operations_map: dict[str, Operation] = getattr(app_api, '_operations', {})
    valid_defaults: list[str] = []

    for op_id in declared_operations:
        spec = operations_map.get(op_id)
        if spec is None or spec.streaming:
            continue
        if spec.principals is not None and PrincipalType.PROCESSOR not in spec.principals:
            continue
        doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
        if doc.exposure == 'all':
            valid_defaults.append(op_id)

    return sorted(set(valid_defaults))


__all__ = [
    'get_default_workspace_operations',
    'get_workspace_operations_catalog',
    'validate_grant_change',
]
