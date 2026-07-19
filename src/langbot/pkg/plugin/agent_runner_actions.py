"""Agent-runner run / runtime / stats / claim actions."""

from __future__ import annotations

from typing import Any
import time


from langbot_plugin.runtime.io import handler


from ..agent.runner.run_ledger_store import TERMINAL_STATUSES

from .agent_run_support import (
    AGENT_RUN_ADMIN_PERMISSION,
    RUNTIME_ADMIN_PERMISSION,
    _plugin_runtime_action,
    _has_agent_runner_admin_permission,
    _deadline_seconds_from_payload,
    _get_run_authorization,
    _authorize_target_run,
    _validate_ledger_only_result_payload,
    _require_runtime_write_ownership,
    _validate_agent_run_session,
    _resolve_run_conversation,
    _run_scope_filters,
    _run_ledger_scope_filters,
    _project_runner_descriptor_for_api,
    _record_agent_runner_admin_action,
)


def register(h):
    @h.action(_plugin_runtime_action('RUN_GET', 'run_get'))
    async def run_get(data: dict[str, Any]) -> handler.ActionResponse:
        """Get one Host-owned run record visible to the current run."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id') or run_id
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run get',
            api_capability='run_get',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            run = await store.get_run(str(target_run_id))
            if not run:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, run)
                if auth_error:
                    return auth_error
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_get',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    detail={'target_run_id': str(target_run_id)},
                )
            return handler.ActionResponse.success(data=run)
        except Exception as e:
            h.ap.logger.error(f'RUN_GET error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run get error: {e}')

    @h.action(_plugin_runtime_action('RUN_LIST', 'run_list'))
    async def run_list(data: dict[str, Any]) -> handler.ActionResponse:
        """List Host-owned runs visible to the current run conversation."""
        run_id = data.get('run_id')
        conversation_id = data.get('conversation_id')
        statuses = data.get('statuses')
        before_cursor = data.get('before_cursor')
        limit = data.get('limit', 50)
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        scope_filters: dict[str, Any] = {}
        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run list',
            api_capability='run_list',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        if not is_admin:
            conversation_id, scope_error = _resolve_run_conversation(
                session,
                conversation_id,
                'Run list',
            )
            if scope_error:
                return scope_error
            scope_filters = _run_ledger_scope_filters(session)

        if not is_admin and not conversation_id:
            return handler.ActionResponse.success(
                data={
                    'items': [],
                    'next_cursor': None,
                    'prev_cursor': None,
                    'has_more': False,
                    'total_count': 0,
                }
            )

        if statuses is not None and not isinstance(statuses, list):
            return handler.ActionResponse.error(message='statuses must be a list')
        try:
            before_id = int(before_cursor) if before_cursor else None
        except (TypeError, ValueError):
            return handler.ActionResponse.error(message='before_cursor must be an integer cursor')

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            items, next_cursor, has_more, total_count = await store.list_runs(
                conversation_id=conversation_id,
                statuses=[str(status) for status in statuses] if statuses else None,
                before_id=before_id,
                limit=limit,
                **scope_filters,
            )
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_list',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    detail={
                        'statuses': [str(status) for status in statuses] if statuses else None,
                        'limit': limit,
                    },
                )
            return handler.ActionResponse.success(
                data={
                    'items': items,
                    'next_cursor': str(next_cursor) if next_cursor else None,
                    'prev_cursor': None,
                    'has_more': has_more,
                    'total_count': total_count,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'RUN_LIST error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run list error: {e}')

    @h.action(_plugin_runtime_action('RUNNER_LIST', 'runner_list'))
    async def runner_list(data: dict[str, Any]) -> handler.ActionResponse:
        """List Host-discovered AgentRunner descriptors."""
        run_id = data.get('run_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin:
            return handler.ActionResponse.error(message='Runner list access not authorized')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runner list',
            api_capability='runner_list',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        include_plugins = data.get('include_plugins')
        if include_plugins is not None and not isinstance(include_plugins, list):
            return handler.ActionResponse.error(message='include_plugins must be a list')

        registry = getattr(h.ap, 'agent_runner_registry', None)
        if registry is None:
            return handler.ActionResponse.success(data={'items': []})

        try:
            runners = await registry.list_runners(
                bound_plugins=[str(item) for item in include_plugins] if include_plugins else None,
                use_cache=bool(data.get('use_cache', True)),
            )
            items = [_project_runner_descriptor_for_api(item) for item in runners]
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    None,
                    action='runner_list',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    detail={
                        'include_plugins': [str(item) for item in include_plugins] if include_plugins else None,
                        'count': len(items),
                    },
                )
            return handler.ActionResponse.success(data={'items': items})
        except Exception as e:
            h.ap.logger.error(f'RUNNER_LIST error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runner list error: {e}')

    @h.action(_plugin_runtime_action('RUN_EVENTS_PAGE', 'run_events_page'))
    async def run_events_page(data: dict[str, Any]) -> handler.ActionResponse:
        """Page result events for one Host-owned run visible to current run."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id') or run_id
        before_cursor = data.get('before_cursor')
        after_cursor = data.get('after_cursor')
        limit = data.get('limit', 50)
        direction = data.get('direction', 'forward')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run events page',
            api_capability='run_events_page',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        try:
            before_sequence = int(before_cursor) if before_cursor else None
            after_sequence = int(after_cursor) if after_cursor else None
        except (TypeError, ValueError):
            return handler.ActionResponse.error(message='run event cursors must be integer sequences')

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            run = await store.get_run(str(target_run_id))
            if not run:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, run)
                if auth_error:
                    return auth_error

            items, next_cursor, prev_cursor, has_more = await store.page_run_events(
                run_id=str(target_run_id),
                before_sequence=before_sequence,
                after_sequence=after_sequence,
                limit=limit,
                direction=str(direction or 'forward'),
            )
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_events_page',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    detail={'target_run_id': str(target_run_id), 'limit': limit},
                )
            return handler.ActionResponse.success(
                data={
                    'items': items,
                    'next_cursor': str(next_cursor) if next_cursor else None,
                    'prev_cursor': str(prev_cursor) if prev_cursor else None,
                    'has_more': has_more,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'RUN_EVENTS_PAGE error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run events page error: {e}')

    @h.action(_plugin_runtime_action('RUN_CANCEL', 'run_cancel'))
    async def run_cancel(data: dict[str, Any]) -> handler.ActionResponse:
        """Request cancellation for one Host-owned run visible to the current run."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id') or run_id
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run cancel',
            api_capability='run_cancel',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            run = await store.get_run(str(target_run_id))
            if not run:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, run)
                if auth_error:
                    return auth_error

            updated = await store.request_cancel(
                run_id=str(target_run_id),
                status_reason=data.get('status_reason') or data.get('reason'),
            )
            if not updated:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_cancel',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    durable_run_id=str(target_run_id),
                    detail={'status_reason': data.get('status_reason') or data.get('reason')},
                )
            return handler.ActionResponse.success(data=updated)
        except Exception as e:
            h.ap.logger.error(f'RUN_CANCEL error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run cancel error: {e}')

    @h.action(_plugin_runtime_action('RUN_APPEND_RESULT', 'run_append_result'))
    async def run_append_result(data: dict[str, Any]) -> handler.ActionResponse:
        """Append one result event for a Host-owned run visible to the current run."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id') or run_id
        caller_plugin_identity = data.get('caller_plugin_identity')
        result = data.get('result') if isinstance(data.get('result'), dict) else {}
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')

        try:
            sequence = int(data.get('sequence') or result.get('sequence'))
        except (TypeError, ValueError):
            return handler.ActionResponse.error(message='sequence is required and must be an integer')

        event_type = data.get('event_type') or data.get('type') or result.get('type')
        if not event_type:
            return handler.ActionResponse.error(message='event_type is required')

        event_data = data.get('data') if isinstance(data.get('data'), dict) else result.get('data')
        usage = data.get('usage') if isinstance(data.get('usage'), dict) else result.get('usage')
        metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else None

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run append result',
            api_capability='run_append_result',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            run = await store.get_run(str(target_run_id))
            if not run:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, run)
                if auth_error:
                    return auth_error
                if run.get('status') in TERMINAL_STATUSES:
                    return handler.ActionResponse.error(
                        message=f'Run append result is not allowed for terminal run {target_run_id}'
                    )
                claim_error = await _require_runtime_write_ownership(
                    store=store,
                    session=session,
                    run=run,
                    data=data,
                    api_name='Run append result',
                )
                if claim_error:
                    return claim_error

            event_payload = event_data if isinstance(event_data, dict) else {}
            payload_error = _validate_ledger_only_result_payload(
                ap=h.ap,
                runner_id=run.get('runner_id'),
                event_type=str(event_type),
                data=event_payload,
            )
            if payload_error:
                return handler.ActionResponse.error(message=payload_error)

            event = await store.append_event(
                run_id=str(target_run_id),
                sequence=sequence,
                event_type=str(event_type),
                data=event_payload,
                usage=usage if isinstance(usage, dict) else None,
                source=str(data.get('source') or result.get('source') or 'runner'),
                metadata=metadata,
            )
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_append_result',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    durable_run_id=str(target_run_id),
                    detail={'event_type': str(event_type), 'sequence': sequence},
                )
            return handler.ActionResponse.success(data=event)
        except Exception as e:
            h.ap.logger.error(f'RUN_APPEND_RESULT error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run append result error: {e}')

    @h.action(_plugin_runtime_action('RUN_FINALIZE', 'run_finalize'))
    async def run_finalize(data: dict[str, Any]) -> handler.ActionResponse:
        """Finalize one Host-owned run visible to the current run."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id') or run_id
        caller_plugin_identity = data.get('caller_plugin_identity')
        status = data.get('status')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')
        if not status:
            return handler.ActionResponse.error(message='status is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run finalize',
            api_capability='run_finalize',
            allow_persistent_authorization=True,
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            run = await store.get_run(str(target_run_id))
            if not run:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, run)
                if auth_error:
                    return auth_error
                claim_error = await _require_runtime_write_ownership(
                    store=store,
                    session=session,
                    run=run,
                    data=data,
                    api_name='Run finalize',
                )
                if claim_error:
                    return claim_error

            updated = await store.finalize_run(
                run_id=str(target_run_id),
                status=str(status),
                status_reason=data.get('status_reason') or data.get('reason'),
                usage=data.get('usage') if isinstance(data.get('usage'), dict) else None,
                cost=data.get('cost') if isinstance(data.get('cost'), dict) else None,
                metadata=data.get('metadata') if isinstance(data.get('metadata'), dict) else None,
            )
            if not updated:
                return handler.ActionResponse.error(message=f'Run {target_run_id} not found')
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_finalize',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    durable_run_id=str(target_run_id),
                    detail={'status': str(status)},
                )
            return handler.ActionResponse.success(data=updated)
        except Exception as e:
            h.ap.logger.error(f'RUN_FINALIZE error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run finalize error: {e}')

    @h.action(_plugin_runtime_action('RUNTIME_REGISTER', 'runtime_register'))
    async def runtime_register(data: dict[str, Any]) -> handler.ActionResponse:
        """Register or update one Host-owned runtime registry record."""
        run_id = data.get('run_id')
        runtime_id = data.get('runtime_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not runtime_id:
            return handler.ActionResponse.error(message='runtime_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runtime register',
            api_capability='runtime_register',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            runtime = await store.register_runtime(
                runtime_id=str(runtime_id),
                status=str(data.get('status') or 'online'),
                display_name=data.get('display_name'),
                endpoint=data.get('endpoint'),
                version=data.get('version'),
                capabilities=data.get('capabilities') if isinstance(data.get('capabilities'), dict) else {},
                labels=data.get('labels') if isinstance(data.get('labels'), dict) else {},
                metadata=data.get('metadata') if isinstance(data.get('metadata'), dict) else {},
                heartbeat_deadline_seconds=_deadline_seconds_from_payload(data),
            )
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='runtime_register',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    target_runtime_id=str(runtime_id),
                    detail={'status': runtime.get('status')},
                )
            return handler.ActionResponse.success(data=runtime)
        except Exception as e:
            h.ap.logger.error(f'RUNTIME_REGISTER error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runtime register error: {e}')

    @h.action(_plugin_runtime_action('RUNTIME_HEARTBEAT', 'runtime_heartbeat'))
    async def runtime_heartbeat(data: dict[str, Any]) -> handler.ActionResponse:
        """Refresh one Host-owned runtime heartbeat."""
        run_id = data.get('run_id')
        runtime_id = data.get('runtime_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not runtime_id:
            return handler.ActionResponse.error(message='runtime_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runtime heartbeat',
            api_capability='runtime_heartbeat',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            runtime = await store.heartbeat_runtime(
                runtime_id=str(runtime_id),
                status=str(data.get('status') or 'online'),
                capabilities=data.get('capabilities') if isinstance(data.get('capabilities'), dict) else None,
                labels=data.get('labels') if isinstance(data.get('labels'), dict) else None,
                metadata=data.get('metadata') if isinstance(data.get('metadata'), dict) else None,
                heartbeat_deadline_seconds=_deadline_seconds_from_payload(data),
            )
            if runtime is None:
                return handler.ActionResponse.error(message=f'Runtime {runtime_id} not found')
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='runtime_heartbeat',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    target_runtime_id=str(runtime_id),
                    detail={'status': runtime.get('status')},
                )
            return handler.ActionResponse.success(data=runtime)
        except Exception as e:
            h.ap.logger.error(f'RUNTIME_HEARTBEAT error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runtime heartbeat error: {e}')

    @h.action(_plugin_runtime_action('RUNTIME_LIST', 'runtime_list'))
    async def runtime_list(data: dict[str, Any]) -> handler.ActionResponse:
        """List Host-owned runtime registry records."""
        run_id = data.get('run_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        _session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runtime list',
            api_capability='runtime_list',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        statuses = data.get('statuses')
        if statuses is not None and not isinstance(statuses, list):
            return handler.ActionResponse.error(message='statuses must be a list')
        labels = data.get('labels') if isinstance(data.get('labels'), dict) else {}

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            runtimes, total_count = await store.list_runtimes(
                statuses=[str(status) for status in statuses] if statuses else None,
                labels=labels,
                limit=data.get('limit', 50),
            )
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='runtime_list',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    detail={
                        'statuses': [str(status) for status in statuses] if statuses else None,
                        'limit': data.get('limit', 50),
                    },
                )
            return handler.ActionResponse.success(
                data={
                    'items': runtimes,
                    'next_cursor': None,
                    'prev_cursor': None,
                    'has_more': False,
                    'total_count': total_count,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'RUNTIME_LIST error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runtime list error: {e}')

    @h.action(_plugin_runtime_action('RUNTIME_RECONCILE', 'runtime_reconcile'))
    async def runtime_reconcile(data: dict[str, Any]) -> handler.ActionResponse:
        """Reconcile stale runtime heartbeats and expired claim leases."""
        run_id = data.get('run_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin:
            return handler.ActionResponse.error(message='Runtime reconcile access not authorized')

        _session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runtime reconcile',
            api_capability='runtime_reconcile',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        stale_after_seconds = data.get('stale_after_seconds')
        if stale_after_seconds is not None:
            try:
                stale_after_seconds = max(float(stale_after_seconds), 0)
            except (TypeError, ValueError):
                return handler.ActionResponse.error(message='stale_after_seconds must be a number')

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            stale_runtimes = await store.mark_stale_runtimes(
                stale_after_seconds=stale_after_seconds,
            )
            released_claims = await store.release_expired_claims()
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='runtime_reconcile',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    detail={
                        'stale_count': len(stale_runtimes),
                        'released_claim_count': len(released_claims),
                    },
                )
            return handler.ActionResponse.success(
                data={
                    'stale_runtimes': stale_runtimes,
                    'released_claims': released_claims,
                    'stale_count': len(stale_runtimes),
                    'released_claim_count': len(released_claims),
                }
            )
        except Exception as e:
            h.ap.logger.error(f'RUNTIME_RECONCILE error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runtime reconcile error: {e}')

    @h.action(_plugin_runtime_action('RUN_STATS', 'run_stats'))
    async def run_stats(data: dict[str, Any]) -> handler.ActionResponse:
        """Get run statistics within a time window (admin-only)."""
        run_id = data.get('run_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin:
            return handler.ActionResponse.error(message='Run stats access not authorized')

        _session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run stats',
            api_capability='run_stats',
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        end_time = data.get('end_time') or int(time.time())
        start_time = data.get('start_time') or (end_time - 3600)  # Default: 1 hour
        runner_id = data.get('runner_id')

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            stats = await store.get_run_stats(
                start_time=start_time,
                end_time=end_time,
                runner_id=runner_id,
            )
            await _record_agent_runner_admin_action(
                h.ap,
                store,
                action='run_stats',
                caller_plugin_identity=caller_plugin_identity,
                permission=AGENT_RUN_ADMIN_PERMISSION,
                detail={
                    'start_time': start_time,
                    'end_time': end_time,
                    'runner_id': runner_id,
                },
            )
            return handler.ActionResponse.success(data=stats)
        except Exception as e:
            h.ap.logger.error(f'RUN_STATS error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run stats error: {e}')

    @h.action(_plugin_runtime_action('RUNTIME_STATS', 'runtime_stats'))
    async def runtime_stats(data: dict[str, Any]) -> handler.ActionResponse:
        """Get runtime registry statistics (admin-only)."""
        run_id = data.get('run_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin:
            return handler.ActionResponse.error(message='Runtime stats access not authorized')

        _session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runtime stats',
            api_capability='runtime_stats',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            stats = await store.get_runtime_stats()
            await _record_agent_runner_admin_action(
                h.ap,
                store,
                action='runtime_stats',
                caller_plugin_identity=caller_plugin_identity,
                permission=RUNTIME_ADMIN_PERMISSION,
                detail={},
            )
            return handler.ActionResponse.success(data=stats)
        except Exception as e:
            h.ap.logger.error(f'RUNTIME_STATS error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runtime stats error: {e}')

    @h.action(_plugin_runtime_action('RUNNER_STATS', 'runner_stats'))
    async def runner_stats(data: dict[str, Any]) -> handler.ActionResponse:
        """Get runner-aggregated statistics (admin-only)."""
        run_id = data.get('run_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        )

        if not is_admin:
            return handler.ActionResponse.error(message='Runner stats access not authorized')

        _session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Runner stats',
            api_capability='runner_stats',
            admin_permission=AGENT_RUN_ADMIN_PERMISSION,
        )
        if error:
            return error

        end_time = data.get('end_time') or int(time.time())
        start_time = data.get('start_time') or (end_time - 3600)  # Default: 1 hour
        limit = min(int(data.get('limit', 50)), 100)

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            stats = await store.get_runner_stats(
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
            await _record_agent_runner_admin_action(
                h.ap,
                store,
                action='runner_stats',
                caller_plugin_identity=caller_plugin_identity,
                permission=AGENT_RUN_ADMIN_PERMISSION,
                detail={
                    'start_time': start_time,
                    'end_time': end_time,
                    'limit': limit,
                },
            )
            return handler.ActionResponse.success(data={'items': stats, 'total_count': len(stats), 'has_more': False})
        except Exception as e:
            h.ap.logger.error(f'RUNNER_STATS error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Runner stats error: {e}')

    @h.action(_plugin_runtime_action('RUN_CLAIM', 'run_claim'))
    async def run_claim(data: dict[str, Any]) -> handler.ActionResponse:
        """Claim one queued run for a runtime lease."""
        run_id = data.get('run_id')
        runtime_id = data.get('runtime_id')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not runtime_id:
            return handler.ActionResponse.error(message='runtime_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run claim',
            api_capability='run_claim',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        runner_ids = data.get('runner_ids')
        if runner_ids is not None and not isinstance(runner_ids, list):
            return handler.ActionResponse.error(message='runner_ids must be a list')

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            scope_filters: dict[str, Any] = {}
            if not is_admin:
                authorization = _get_run_authorization(session)
                session_runner_id = session.get('runner_id') or authorization.get('runner_id')
                if not session_runner_id:
                    return handler.ActionResponse.error(message='Run claim is not available without a runner_id')
                if runner_ids and any(str(item) != session_runner_id for item in runner_ids):
                    return handler.ActionResponse.error(message='Run claim runner_ids are not accessible by this run')
                runner_ids = [session_runner_id]
                scope_filters = {
                    'conversation_id': authorization.get('conversation_id'),
                    **_run_scope_filters(session),
                }
            run = await store.claim_next_run(
                runtime_id=str(runtime_id),
                queue_name=data.get('queue_name'),
                lease_seconds=data.get('lease_seconds', 60),
                runner_ids=[str(item) for item in runner_ids] if runner_ids else None,
                **scope_filters,
            )
            if run is None:
                return handler.ActionResponse.error(message='No queued run available')
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_claim',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    durable_run_id=str(run.get('run_id')),
                    target_runtime_id=str(runtime_id),
                    detail={
                        'queue_name': data.get('queue_name'),
                        'runner_ids': [str(item) for item in runner_ids] if runner_ids else None,
                    },
                )
            return handler.ActionResponse.success(data=run)
        except Exception as e:
            h.ap.logger.error(f'RUN_CLAIM error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run claim error: {e}')

    @h.action(_plugin_runtime_action('RUN_RENEW_CLAIM', 'run_renew_claim'))
    async def run_renew_claim(data: dict[str, Any]) -> handler.ActionResponse:
        """Renew one run claim lease."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id')
        runtime_id = data.get('runtime_id')
        claim_token = data.get('claim_token')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')
        if not runtime_id:
            return handler.ActionResponse.error(message='runtime_id is required')
        if not claim_token:
            return handler.ActionResponse.error(message='claim_token is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run renew claim',
            api_capability='run_renew_claim',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            current = await store.get_run(str(target_run_id))
            if not current or current.get('claimed_by_runtime_id') != runtime_id:
                return handler.ActionResponse.error(message=f'Run claim {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, current)
                if auth_error:
                    return auth_error
            run = await store.renew_claim(
                run_id=str(target_run_id),
                claim_token=str(claim_token),
                runtime_id=str(runtime_id),
                lease_seconds=data.get('lease_seconds', 60),
            )
            if run is None:
                return handler.ActionResponse.error(message=f'Run claim {target_run_id} not found')
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_renew_claim',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    durable_run_id=str(target_run_id),
                    target_runtime_id=str(runtime_id),
                    detail={'lease_seconds': data.get('lease_seconds', 60)},
                )
            return handler.ActionResponse.success(data=run)
        except Exception as e:
            h.ap.logger.error(f'RUN_RENEW_CLAIM error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run renew claim error: {e}')

    @h.action(_plugin_runtime_action('RUN_RELEASE_CLAIM', 'run_release_claim'))
    async def run_release_claim(data: dict[str, Any]) -> handler.ActionResponse:
        """Release one run claim lease."""
        run_id = data.get('run_id')
        target_run_id = data.get('target_run_id')
        runtime_id = data.get('runtime_id')
        claim_token = data.get('claim_token')
        caller_plugin_identity = data.get('caller_plugin_identity')
        is_admin = _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            RUNTIME_ADMIN_PERMISSION,
        )

        if not is_admin and not run_id:
            return handler.ActionResponse.error(message='run_id is required')
        if not target_run_id:
            return handler.ActionResponse.error(message='target_run_id is required')
        if not runtime_id:
            return handler.ActionResponse.error(message='runtime_id is required')
        if not claim_token:
            return handler.ActionResponse.error(message='claim_token is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Run release claim',
            api_capability='run_release_claim',
            admin_permission=RUNTIME_ADMIN_PERMISSION,
        )
        if error:
            return error

        from ..agent.runner.run_ledger_store import RunLedgerStore

        store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())

        try:
            current = await store.get_run(str(target_run_id))
            if not current or current.get('claimed_by_runtime_id') != runtime_id:
                return handler.ActionResponse.error(message=f'Run claim {target_run_id} not found')
            if not is_admin:
                auth_error = _authorize_target_run(session, current)
                if auth_error:
                    return auth_error
                release_status = str(data.get('status') or 'queued')
                if release_status in TERMINAL_STATUSES:
                    return handler.ActionResponse.error(
                        message='Run release claim cannot finalize a run; use run_finalize'
                    )
            run = await store.release_claim(
                run_id=str(target_run_id),
                claim_token=str(claim_token),
                runtime_id=str(runtime_id),
                status=str(data.get('status') or 'queued'),
                status_reason=data.get('status_reason') or data.get('reason'),
            )
            if run is None:
                return handler.ActionResponse.error(message=f'Run claim {target_run_id} not found')
            if is_admin:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_release_claim',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=RUNTIME_ADMIN_PERMISSION,
                    durable_run_id=str(target_run_id),
                    target_runtime_id=str(runtime_id),
                    detail={
                        'status': str(data.get('status') or 'queued'),
                        'status_reason': data.get('status_reason') or data.get('reason'),
                    },
                )
            return handler.ActionResponse.success(data=run)
        except Exception as e:
            h.ap.logger.error(f'RUN_RELEASE_CLAIM error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Run release claim error: {e}')
