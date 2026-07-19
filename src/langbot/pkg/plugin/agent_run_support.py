"""Agent-runner protocol support: shared constants and authorization/scope/projection helpers extracted from handler.py."""

from __future__ import annotations

from typing import Any, Union
import json
import time

import sqlalchemy

from langbot_plugin.runtime.io import handler
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction,
)


from ..core import app
from ..agent.runner.session_registry import get_session_registry
from ..agent.runner.result_normalizer import MAX_RESULT_SIZE_BYTES, STRICT_RESULT_PAYLOADS


class _RuntimeActionName:
    def __init__(self, value: str):
        self.value = value


AGENT_RUN_ADMIN_PERMISSION = 'agent_run:admin'
RUNTIME_ADMIN_PERMISSION = 'runtime:admin'
AGENT_RUNNER_ADMIN_PERMISSION = 'agent_runner:admin'
LEDGER_ONLY_SIDE_EFFECTING_RESULT_TYPES = {
    'message.delta',
    'message.completed',
    'state.updated',
    'run.completed',
    'run.failed',
}


def _plugin_runtime_action(name: str, value: str) -> Any:
    return getattr(PluginToRuntimeAction, name, _RuntimeActionName(value))


def _normalize_permission_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {permission.strip() for permission in value.split(',') if permission.strip()}
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, dict):
        return {str(item).strip() for item, enabled in value.items() if enabled and str(item).strip()}
    return set()


def _iter_agent_runner_admin_plugin_configs(ap: app.Application) -> list[dict[str, Any]]:
    instance_config = getattr(ap, 'instance_config', None)
    config_data = getattr(instance_config, 'data', {}) if instance_config is not None else {}
    if not isinstance(config_data, dict):
        return []
    agent_runner_config = config_data.get('agent_runner', {})
    if not isinstance(agent_runner_config, dict):
        return []
    raw_admin_plugins = agent_runner_config.get('admin_plugins', [])
    if isinstance(raw_admin_plugins, dict):
        items: list[dict[str, Any]] = []
        for identity, entry in raw_admin_plugins.items():
            if isinstance(entry, dict):
                merged = dict(entry)
                merged.setdefault('identity', identity)
                items.append(merged)
            else:
                items.append({'identity': identity, 'permissions': entry})
        return items
    if isinstance(raw_admin_plugins, list):
        return [item for item in raw_admin_plugins if isinstance(item, dict)]
    return []


def _agent_runner_admin_permissions(ap: app.Application, plugin_identity: str | None) -> set[str]:
    if not isinstance(plugin_identity, str) or not plugin_identity.strip():
        return set()
    normalized_identity = plugin_identity.strip()
    permissions: set[str] = set()
    for entry in _iter_agent_runner_admin_plugin_configs(ap):
        if entry.get('enabled', True) is False:
            continue
        identity = entry.get('identity') or entry.get('plugin_identity') or entry.get('plugin') or entry.get('id')
        if identity != normalized_identity:
            continue
        permissions.update(_normalize_permission_set(entry.get('permissions')))
        permissions.update(_normalize_permission_set(entry.get('scopes')))
    return permissions


def _has_agent_runner_admin_permission(
    ap: app.Application,
    plugin_identity: str | None,
    permission: str,
) -> bool:
    permissions = _agent_runner_admin_permissions(ap, plugin_identity)
    if not permissions:
        return False
    domain = permission.split(':', 1)[0]
    return bool(
        permission in permissions
        or f'{domain}:*' in permissions
        or AGENT_RUNNER_ADMIN_PERMISSION in permissions
        or '*' in permissions
    )


def _deadline_seconds_from_payload(data: dict[str, Any], default: int = 60) -> int:
    deadline_at = data.get('heartbeat_deadline_at')
    if deadline_at is not None:
        try:
            return max(int(float(deadline_at) - time.time()), 1)
        except (TypeError, ValueError):
            pass
    try:
        return max(int(data.get('heartbeat_ttl_seconds') or default), 1)
    except (TypeError, ValueError):
        return default


def _get_run_authorization(session: dict[str, Any]) -> dict[str, Any]:
    """Return the run-scoped authorization snapshot."""
    return session['authorization']


def _run_matches_run_scope(session: dict[str, Any], run: dict[str, Any]) -> bool:
    authorization = _get_run_authorization(session)
    session_run_id = session.get('run_id')
    if run.get('run_id') == session_run_id:
        return True
    session_runner_id = session.get('runner_id') or authorization.get('runner_id')
    if not session_runner_id or run.get('runner_id') != session_runner_id:
        return False
    if not authorization.get('conversation_id'):
        return False
    if run.get('conversation_id') != authorization.get('conversation_id'):
        return False
    if authorization.get('bot_id') is not None and authorization.get('bot_id') != run.get('bot_id'):
        return False
    if authorization.get('workspace_id') is not None and authorization.get('workspace_id') != run.get('workspace_id'):
        return False
    if authorization.get('thread_id') != run.get('thread_id'):
        return False
    return True


def _authorize_target_run(
    session: dict[str, Any],
    run: dict[str, Any],
) -> handler.ActionResponse | None:
    """Authorize non-admin target-run access against scope and runner owner."""
    if _run_matches_run_scope(session, run):
        return None
    return handler.ActionResponse.error(message=f'Run {run.get("run_id")} is not accessible by this run')


def _validate_ledger_only_result_payload(
    *,
    ap: app.Application,
    runner_id: str | None,
    event_type: str,
    data: dict[str, Any],
) -> str | None:
    """Validate result payloads that can be safely stored without side effects."""
    try:
        result_json = json.dumps({'type': event_type, 'data': data})
    except (TypeError, ValueError) as exc:
        return f'event data must be JSON serializable: {exc}'
    if len(result_json) > MAX_RESULT_SIZE_BYTES:
        return f'event payload exceeds {MAX_RESULT_SIZE_BYTES} bytes'

    payload_model = STRICT_RESULT_PAYLOADS.get(event_type)
    if payload_model is None:
        return f'unknown result type: {event_type}'
    try:
        payload_model.model_validate(data)
    except Exception as exc:
        return f'invalid {event_type} payload: {exc}'

    if event_type in LEDGER_ONLY_SIDE_EFFECTING_RESULT_TYPES:
        if runner_id:
            ap.logger.warning(
                f'Runner {runner_id} attempted ledger-only append for side-effecting result type {event_type}'
            )
        return f'{event_type} must be emitted through the canonical runner result path'
    return None


async def _require_runtime_write_ownership(
    *,
    store: Any,
    session: dict[str, Any],
    run: dict[str, Any],
    data: dict[str, Any],
    api_name: str,
) -> handler.ActionResponse | None:
    """Require current-run ownership or an active runtime claim for run writes."""
    if run.get('run_id') == session.get('run_id') and run.get('status') != 'claimed':
        return None

    runtime_id = data.get('runtime_id')
    claim_token = data.get('claim_token')
    if not runtime_id or not claim_token:
        return handler.ActionResponse.error(
            message=f'{api_name} requires active claim ownership for target run {run.get("run_id")}'
        )

    if not await store.validate_active_claim(
        run_id=str(run.get('run_id')),
        runtime_id=str(runtime_id),
        claim_token=str(claim_token),
    ):
        return handler.ActionResponse.error(
            message=f'{api_name} claim ownership is not active for target run {run.get("run_id")}'
        )

    return None


def _resolve_state_scope(
    session: dict[str, Any],
    scope: str,
) -> tuple[dict[str, Any] | None, str | None, handler.ActionResponse | None]:
    """Resolve state policy/context for an authorized run scope."""
    authorization = _get_run_authorization(session)
    state_policy = authorization['state_policy']

    if not state_policy.get('enable_state', True):
        return None, None, handler.ActionResponse.error(message='State access is disabled by binding policy')

    state_scopes = state_policy.get('state_scopes', ['conversation', 'actor'])
    if scope not in state_scopes:
        return None, None, handler.ActionResponse.error(message=f'Scope "{scope}" is not enabled by binding policy')

    state_context = authorization['state_context']
    scope_key = state_context.get('scope_keys', {}).get(scope)
    if not scope_key:
        return None, None, handler.ActionResponse.error(message=f'Scope key not available for scope "{scope}"')

    return state_context, scope_key, None


async def _validate_agent_run_session(
    run_id: str,
    caller_plugin_identity: str | None,
    ap: app.Application,
    api_name: str,
    api_capability: str | None = None,
    allow_persistent_authorization: bool = False,
    admin_permission: str | None = None,
) -> Union[tuple[None, handler.ActionResponse], tuple[Any, None]]:
    """Validate an AgentRunner pull API run session and run-scoped API access."""
    if (
        not run_id
        and admin_permission
        and _has_agent_runner_admin_permission(
            ap,
            caller_plugin_identity,
            admin_permission,
        )
    ):
        return {
            'run_id': run_id,
            'runner_id': None,
            'query_id': None,
            'plugin_identity': caller_plugin_identity,
            'authorization': {},
            'status': {},
            'steering_queue': [],
        }, None

    session_registry = get_session_registry()
    session = await session_registry.get(run_id)
    if not session:
        if allow_persistent_authorization:
            session = await _load_persistent_agent_run_session(run_id, ap, api_name)
        if not session:
            return None, handler.ActionResponse.error(message=f'Run session {run_id} not found or expired')

    session_plugin_identity = session.get('plugin_identity')
    if not isinstance(session_plugin_identity, str) or not session_plugin_identity.strip():
        ap.logger.warning(f'{api_name}: run_id {run_id} has no plugin_identity')
        return None, handler.ActionResponse.error(message=f'Run session {run_id} has no plugin_identity')
    if not caller_plugin_identity:
        return None, handler.ActionResponse.error(message=f'caller_plugin_identity is required for run_id {run_id}')
    if caller_plugin_identity != session_plugin_identity:
        ap.logger.warning(
            f'{api_name}: caller_plugin_identity {caller_plugin_identity} '
            f'does not match session plugin_identity {session_plugin_identity}'
        )
        return None, handler.ActionResponse.error(message=f'Plugin identity mismatch for run_id {run_id}')

    if api_capability:
        available_apis = _get_run_authorization(session).get('available_apis', {})
        has_admin_permission = bool(admin_permission) and _has_agent_runner_admin_permission(
            ap,
            caller_plugin_identity,
            admin_permission,
        )
        if not available_apis.get(api_capability, False) and not has_admin_permission:
            return None, handler.ActionResponse.error(message=f'{api_name} access not authorized')

    return session, None


async def _load_persistent_agent_run_session(
    run_id: str,
    ap: app.Application,
    api_name: str,
) -> dict[str, Any] | None:
    """Load an expired run session from the AgentRun authorization snapshot."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        from ..entity.persistence.agent_run import AgentRun

        engine = ap.persistence_mgr.get_db_engine()
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db_session:
            result = await db_session.execute(sqlalchemy.select(AgentRun).where(AgentRun.run_id == run_id))
            run = result.scalars().first()
    except Exception as e:
        ap.logger.error(f'{api_name}: failed to load persistent authorization for run_id {run_id}: {e}', exc_info=True)
        return None

    if run is None:
        return None

    try:
        authorization = json.loads(run.authorization_json) if run.authorization_json else {}
    except (TypeError, ValueError) as e:
        ap.logger.warning(f'{api_name}: run_id {run_id} has invalid authorization_json: {e}')
        return None

    if not isinstance(authorization, dict):
        ap.logger.warning(f'{api_name}: run_id {run_id} authorization_json is not an object')
        return None

    return {
        'run_id': run.run_id,
        'runner_id': authorization.get('runner_id') or run.runner_id,
        'query_id': None,
        'plugin_identity': authorization.get('plugin_identity'),
        'authorization': authorization,
        'status': {},
        'steering_queue': [],
    }


def _resolve_run_conversation(
    session: dict[str, Any],
    requested_conversation_id: str | None,
    api_name: str,
) -> tuple[str | None, handler.ActionResponse | None]:
    """Resolve and enforce current-run conversation scope."""
    session_conversation_id = _get_run_authorization(session).get('conversation_id')

    if requested_conversation_id:
        if not session_conversation_id:
            return None, handler.ActionResponse.error(message=f'{api_name} is not available without a run conversation')
        if requested_conversation_id != session_conversation_id:
            return None, handler.ActionResponse.error(
                message=f'Conversation {requested_conversation_id} is not accessible by this run'
            )
        return requested_conversation_id, None

    return session_conversation_id, None


def _run_scope_filters(session: dict[str, Any]) -> dict[str, Any]:
    authorization = _get_run_authorization(session)
    return {
        'bot_id': authorization.get('bot_id'),
        'workspace_id': authorization.get('workspace_id'),
        'thread_id': authorization.get('thread_id'),
        'strict_thread': True,
    }


def _run_ledger_scope_filters(session: dict[str, Any]) -> dict[str, Any]:
    authorization = _get_run_authorization(session)
    filters = _run_scope_filters(session)
    filters['runner_id'] = session.get('runner_id') or authorization.get('runner_id')
    return filters


def _event_matches_run_scope(session: dict[str, Any], event: dict[str, Any]) -> bool:
    authorization = _get_run_authorization(session)
    if authorization.get('conversation_id') != event.get('conversation_id'):
        return False
    if authorization.get('bot_id') is not None and authorization.get('bot_id') != event.get('bot_id'):
        return False
    if authorization.get('workspace_id') is not None and authorization.get('workspace_id') != event.get('workspace_id'):
        return False
    if authorization.get('thread_id') != event.get('thread_id'):
        return False
    return True


def _project_event_record_for_api(event: dict[str, Any]) -> dict[str, Any]:
    """Project EventLogStore rows onto the SDK AgentEventRecord DTO."""
    seq = event.get('seq') or event.get('id')
    return {
        'event_id': event.get('event_id'),
        'event_type': event.get('event_type'),
        'event_time': event.get('event_time'),
        'source': event.get('source'),
        'bot_id': event.get('bot_id'),
        'workspace_id': event.get('workspace_id'),
        'conversation_id': event.get('conversation_id'),
        'thread_id': event.get('thread_id'),
        'actor_type': event.get('actor_type'),
        'actor_id': event.get('actor_id'),
        'actor_name': event.get('actor_name'),
        'subject_type': event.get('subject_type'),
        'subject_id': event.get('subject_id'),
        'input_summary': event.get('input_summary'),
        'input_ref': event.get('input_ref'),
        'raw_ref': event.get('raw_ref'),
        'seq': seq,
        'cursor': event.get('cursor') or (str(seq) if seq is not None else None),
        'created_at': event.get('created_at'),
        'metadata': event.get('metadata') or {},
    }


def _project_runner_descriptor_for_api(descriptor: Any) -> dict[str, Any]:
    """Project an AgentRunnerDescriptor-like object onto a JSON dict."""
    if isinstance(descriptor, dict):
        return dict(descriptor)
    if hasattr(descriptor, 'model_dump'):
        return descriptor.model_dump(mode='json')
    return {
        'id': getattr(descriptor, 'id', None),
        'source': getattr(descriptor, 'source', None),
        'label': getattr(descriptor, 'label', {}),
        'description': getattr(descriptor, 'description', None),
        'plugin_author': getattr(descriptor, 'plugin_author', None),
        'plugin_name': getattr(descriptor, 'plugin_name', None),
        'runner_name': getattr(descriptor, 'runner_name', None),
        'plugin_version': getattr(descriptor, 'plugin_version', None),
        'config_schema': getattr(descriptor, 'config_schema', []),
        'capabilities': getattr(descriptor, 'capabilities', {}),
        'permissions': getattr(descriptor, 'permissions', {}),
        'raw_manifest': getattr(descriptor, 'raw_manifest', {}),
    }


async def _record_agent_runner_admin_action(
    ap: app.Application,
    store: Any,
    *,
    action: str,
    caller_plugin_identity: str | None,
    permission: str,
    durable_run_id: str | None = None,
    target_runtime_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Record a small audit trail for privileged AgentRunner operations."""
    audit_data: dict[str, Any] = {
        'action': action,
        'caller_plugin_identity': caller_plugin_identity,
        'permission': permission,
    }
    if durable_run_id:
        audit_data['target_run_id'] = durable_run_id
    if target_runtime_id:
        audit_data['target_runtime_id'] = target_runtime_id
    if detail:
        audit_data['detail'] = detail

    ap.logger.info('Agent runner admin action: %s', audit_data)
    if not durable_run_id or store is None or not hasattr(store, 'append_audit_event'):
        return

    try:
        await store.append_audit_event(
            run_id=str(durable_run_id),
            event_type=f'admin.{action}',
            data=audit_data,
            metadata={'permission': permission},
        )
    except Exception as exc:
        ap.logger.warning(f'Failed to record AgentRunner admin audit event: {exc}', exc_info=True)
