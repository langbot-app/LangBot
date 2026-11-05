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


def validate_operation_preferences(ap, editor_context, old_ids, new_ids) -> list[str]:
    from .plugin_permissions import expand_declaration

    if not isinstance(new_ids, list) or any(not isinstance(item, str) or '*' in item for item in new_ids):
        raise ApplicationAPIException(ApplicationAPIError('invalid_input', 'Expected concrete operation IDs', 400))
    return expand_declaration(ap, {'workspace_operations': new_ids})['workspace_operations']


def validate_grant_change(
    ap: Any,
    editor_context: RequestContext,
    old_ids: Iterable[str] | None,
    new_ids: Iterable[str] | None,
    *,
    old_capabilities: Iterable[str] = (),
    new_capabilities: Iterable[str] = (),
    principal_type: PrincipalType = PrincipalType.PROCESSOR,
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

    from .plugin_capabilities import CAPABILITY_PERMISSIONS

    if not isinstance(new_capabilities, (list, tuple, set, frozenset)) or any(
        not isinstance(item, str) for item in new_capabilities
    ):
        raise ApplicationAPIException(ApplicationAPIError('invalid_input', 'Invalid capabilities', 400))
    invalid_capabilities = sorted(set(new_capabilities) - CAPABILITY_PERMISSIONS.keys())
    if invalid_capabilities:
        raise ApplicationAPIException(
            ApplicationAPIError(
                'invalid_input',
                'Unknown capabilities',
                400,
                {'invalid_capabilities': invalid_capabilities},
            )
        )
    added_capabilities = sorted(set(new_capabilities) - set(old_capabilities))

    if not added_ids and not added_capabilities:
        return normalized_new

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

        if spec.principals is not None and principal_type not in spec.principals:
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

    if getattr(getattr(editor_context, 'principal', None), 'principal_type', None) not in {
        PrincipalType.ACCOUNT,
        PrincipalType.SUPPORT_ADMIN,
    }:
        raise ApplicationAPIException(
            ApplicationAPIError(
                'permission_denied',
                'This principal cannot grant permissions',
                403,
                {'operations': added_ids, 'denied_operations': added_ids, 'denied_capabilities': added_capabilities},
            )
        )

    denied_capabilities = [
        name
        for name in added_capabilities
        if not all(has_permission(editor_context, permission) for permission in CAPABILITY_PERMISSIONS[name])
    ]
    if denied_ids or denied_capabilities:
        raise ApplicationAPIException(
            ApplicationAPIError(
                code='permission_denied',
                message=f'Permission denied for workspace operations: {denied_ids}',
                status_code=403,
                details={
                    'operations': denied_ids,
                    'denied_operations': denied_ids,
                    'denied_capabilities': denied_capabilities,
                },
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


__all__ = [
    'get_workspace_operations_catalog',
    'validate_grant_change',
    'validate_operation_preferences',
]
