"""Access layer for authorized application operations."""

from __future__ import annotations

import copy
import dataclasses
import logging
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import TypeAdapter

from ..authz import has_permission
from ..context import RequestContext
from ..secrets import redact_secrets
from .contracts import Operation
from .errors import error_from_exception
from .operation_docs import DOMAINS, get_operation_doc

logger = logging.getLogger(__name__)

_VALID_CONSUMERS: frozenset[str] = frozenset({'assistant', 'processor'})


@dataclasses.dataclass(frozen=True, slots=True)
class GrantedOperation:
    """Serializable operation metadata presented to authorized consumers."""

    id: str
    domain: str
    label: dict[str, str]
    summary: str
    description: str
    risk: Literal['read', 'write', 'dangerous']
    side_effect: bool
    permission: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'domain': self.domain,
            'label': self.label,
            'summary': self.summary,
            'description': self.description,
            'risk': self.risk,
            'side_effect': self.side_effect,
            'permission': self.permission,
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
        }

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self) -> tuple[str, ...]:
        return (
            'id',
            'domain',
            'label',
            'summary',
            'description',
            'risk',
            'side_effect',
            'permission',
            'input_schema',
            'output_schema',
        )

    def __iter__(self):
        return iter(self.keys())


def _clean_input_schema(spec: Operation) -> dict[str, Any]:
    schema = copy.deepcopy(spec.input_type.model_json_schema())
    properties = schema.get('properties')
    if isinstance(properties, dict) and 'include_secret' in properties:
        del properties['include_secret']
    required = schema.get('required')
    if isinstance(required, list) and 'include_secret' in required:
        schema['required'] = [item for item in required if item != 'include_secret']
    return schema


def _build_granted_operation(spec: Operation) -> GrantedOperation:
    doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
    perm = spec.permission
    perm_str = perm.value if hasattr(perm, 'value') else str(perm)
    return GrantedOperation(
        id=spec.operation_id,
        domain=doc.domain,
        label=doc.label,
        summary=doc.summary,
        description=doc.description,
        risk=doc.risk,
        side_effect=spec.side_effect,
        permission=perm_str,
        input_schema=_clean_input_schema(spec),
        output_schema=TypeAdapter(spec.output_type).json_schema(),
    )


def list_granted(
    ap: Any,
    context: RequestContext,
    *,
    consumer: Literal['assistant', 'processor'],
    granted: Iterable[str] | None = None,
) -> list[GrantedOperation]:
    """List all authorized operations for the given consumer and identity."""
    if consumer not in _VALID_CONSUMERS:
        raise ValueError(f'Invalid consumer: {consumer!r}; must be one of {sorted(_VALID_CONSUMERS)}')

    app_api = getattr(ap, 'application_api', None)
    if app_api is None:
        return []

    operations_map: dict[str, Operation] = getattr(app_api, '_operations', {})
    principal_type = context.principal.principal_type

    if consumer == 'assistant':
        granted_ops: list[GrantedOperation] = []
        for spec in operations_map.values():
            if spec.streaming:
                continue
            if spec.principals is not None and principal_type not in spec.principals:
                continue
            doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
            if doc.exposure not in {'assistant', 'all'}:
                continue
            if not has_permission(context, spec.permission):
                continue
            granted_ops.append(_build_granted_operation(spec))
        return granted_ops

    # consumer == 'processor'
    ctx_allowed = getattr(context, 'allowed_operation_ids', None)
    ctx_allowed_set = frozenset(ctx_allowed) if ctx_allowed is not None else frozenset()

    if granted is None:
        candidate_ids = list(ctx_allowed) if ctx_allowed is not None else []
    else:
        candidate_ids = list(granted)

    seen: set[str] = set()
    granted_ops = []
    discarded: list[tuple[str, str]] = []

    for op_id in candidate_ids:
        if op_id in seen:
            continue
        seen.add(op_id)
        if op_id not in ctx_allowed_set:
            discarded.append((op_id, 'not_in_context_allowed_operation_ids'))
            continue
        spec = operations_map.get(op_id)
        if spec is None:
            discarded.append((op_id, 'not_found'))
            continue
        if spec.streaming:
            discarded.append((op_id, 'streaming'))
            continue
        if spec.principals is not None and principal_type not in spec.principals:
            discarded.append((op_id, 'principal_not_allowed'))
            continue
        doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
        if doc.exposure != 'all':
            discarded.append((op_id, f'exposure_{doc.exposure}'))
            continue
        granted_ops.append(_build_granted_operation(spec))

    if discarded:
        logger.warning('Discarded %d invalid operation(s) for processor: %s', len(discarded), discarded)

    return granted_ops


def domains(ops: Iterable[Any]) -> list[dict[str, Any]]:
    """Return summary statistics of domains present in the granted operations list."""
    counts: dict[str, int] = {}
    for op in ops:
        domain = getattr(op, 'domain', None)
        if domain is None and isinstance(op, Mapping):
            domain = op.get('domain')
        if domain is None and isinstance(op, str):
            domain = op.split('.')[0]
        if domain:
            counts[domain] = counts.get(domain, 0) + 1

    result = []
    for domain, count in sorted(counts.items()):
        meta = DOMAINS.get(domain, {})
        label = meta.get('label', {'zh_Hans': domain, 'en_US': domain.capitalize()})
        summary = meta.get('summary', '')
        result.append(
            {
                'domain': domain,
                'label': label,
                'summary': summary,
                'count': count,
            }
        )
    return result


def requires_confirmation(op: Any) -> bool:
    """Return whether an operation requires interactive confirmation before execution."""
    if isinstance(op, str):
        return get_operation_doc(op).risk != 'read'
    if hasattr(op, 'risk'):
        return getattr(op, 'risk') != 'read'
    if isinstance(op, Mapping):
        risk = op.get('risk')
        if risk is not None:
            return risk != 'read'
        op_id = op.get('id') or op.get('operation_id')
        if op_id:
            return get_operation_doc(str(op_id)).risk != 'read'
    return True


def _collect_input_values(data: Any) -> list[str]:
    values: list[str] = []
    if isinstance(data, Mapping):
        for v in data.values():
            values.extend(_collect_input_values(v))
    elif isinstance(data, (list, tuple, set, frozenset)):
        for v in data:
            values.extend(_collect_input_values(v))
    elif isinstance(data, (str, int, float)) and data is not None and data is not True and data is not False:
        s = str(data).strip()
        if len(s) >= 4:
            values.append(s)
    return values


def _sanitize_error_message(message: str, arguments: Mapping[str, Any]) -> str:
    if not message:
        return message
    input_values = sorted(set(_collect_input_values(arguments)), key=len, reverse=True)
    for val in input_values:
        if val in message:
            message = message.replace(val, '[REDACTED]')
    return message


def _is_operation_granted(
    spec: Operation,
    context: RequestContext,
    *,
    consumer: Literal['assistant', 'processor'],
    granted: Iterable[str] | None = None,
) -> bool:
    if spec.streaming:
        return False
    if spec.principals is not None and context.principal.principal_type not in spec.principals:
        return False
    doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)
    if consumer == 'assistant':
        if doc.exposure not in {'assistant', 'all'}:
            return False
        return has_permission(context, spec.permission)

    # consumer == 'processor'
    if doc.exposure != 'all':
        return False
    ctx_allowed = getattr(context, 'allowed_operation_ids', None)
    if ctx_allowed is None or spec.operation_id not in ctx_allowed:
        return False
    if granted is not None and spec.operation_id not in set(granted):
        return False
    return True


async def call(
    ap: Any,
    context: RequestContext,
    operation_id: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    consumer: Literal['assistant', 'processor'],
    granted: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Directly execute an authorized operation without raising exceptions."""
    app_api = getattr(ap, 'application_api', None)
    operations_map: dict[str, Operation] = getattr(app_api, '_operations', {}) if app_api is not None else {}
    spec = operations_map.get(operation_id)

    if spec is None or not _is_operation_granted(spec, context, consumer=consumer, granted=granted):
        return {
            'ok': False,
            'error': {
                'code': 'not_found',
                'message': 'Operation not found',
            },
        }

    clean_arguments = {k: v for k, v in (arguments or {}).items() if k != 'include_secret'}
    doc = get_operation_doc(spec.operation_id, side_effect=spec.side_effect)

    try:
        raw_result = await app_api.execute(operation_id, context, clean_arguments)
        return {
            'ok': True,
            'result': redact_secrets(raw_result),
            'operation': {
                'id': operation_id,
                'risk': doc.risk,
                'side_effect': spec.side_effect,
            },
        }
    except Exception as exc:
        error = error_from_exception(exc, operation_id=operation_id)
        sanitized_message = _sanitize_error_message(error.message, clean_arguments)
        return {
            'ok': False,
            'error': {
                'code': error.code,
                'message': sanitized_message,
            },
        }


__all__ = [
    'GrantedOperation',
    'call',
    'domains',
    'list_granted',
    'requires_confirmation',
]
