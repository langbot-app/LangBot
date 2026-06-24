"""Agent-runner run / runtime / stats / claim actions."""

from __future__ import annotations

from typing import Any
import asyncio
import time
import uuid


from langbot_plugin.runtime.io import handler
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput


from ..agent.runner.host_models import (
    AgentBinding,
    AgentEventEnvelope,
    BindingScope,
    DeliveryPolicy,
    ResourcePolicy,
    StatePolicy,
)
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


def _dict_payload(value: Any, *, field_name: str) -> tuple[dict[str, Any], handler.ActionResponse | None]:
    if value is None:
        return {}, None
    if not isinstance(value, dict):
        return {}, handler.ActionResponse.error(message=f'{field_name} must be an object')
    return dict(value), None


def _build_run_create_event(data: dict[str, Any], *, run_id: str) -> tuple[AgentEventEnvelope | None, handler.ActionResponse | None]:
    event_payload, error = _dict_payload(data.get('event'), field_name='event')
    if error:
        return None, error

    input_payload = event_payload.get('input', data.get('input'))
    if input_payload is None:
        input_payload = {
            'text': data.get('text'),
            'contents': [],
            'attachments': [],
        }
    if not isinstance(input_payload, dict):
        return None, handler.ActionResponse.error(message='input must be an object')

    delivery_payload = event_payload.get('delivery', data.get('delivery'))
    if delivery_payload is None:
        delivery_payload = {
            'surface': 'api',
            'reply_target': None,
            'supports_streaming': False,
            'supports_edit': False,
            'supports_reaction': False,
            'platform_capabilities': {},
        }
    if not isinstance(delivery_payload, dict):
        return None, handler.ActionResponse.error(message='delivery must be an object')

    event_data = event_payload.get('data', data.get('data'))
    if event_data is None:
        event_data = {}
    if not isinstance(event_data, dict):
        return None, handler.ActionResponse.error(message='event data must be an object')

    event_type = str(event_payload.get('event_type') or data.get('event_type') or 'api.invoked')
    source = str(event_payload.get('source') or data.get('source') or 'api')
    event_id = str(event_payload.get('event_id') or data.get('event_id') or f'{source}:{run_id}')
    event_time = event_payload.get('event_time', data.get('event_time'))
    if event_time is None:
        event_time = int(time.time())

    try:
        envelope = AgentEventEnvelope(
            event_id=event_id,
            event_type=event_type,
            event_time=int(event_time) if isinstance(event_time, (int, float, str)) else None,
            source=source,
            source_event_type=event_payload.get('source_event_type') or data.get('source_event_type') or event_type,
            bot_id=event_payload.get('bot_id', data.get('bot_id')),
            workspace_id=event_payload.get('workspace_id', data.get('workspace_id')),
            conversation_id=event_payload.get('conversation_id', data.get('conversation_id')),
            thread_id=event_payload.get('thread_id', data.get('thread_id')),
            actor=event_payload.get('actor', data.get('actor')),
            subject=event_payload.get('subject', data.get('subject')),
            input=AgentInput.model_validate(input_payload),
            delivery=DeliveryContext.model_validate(delivery_payload),
            raw_ref=event_payload.get('raw_ref', data.get('raw_ref')),
            data=event_data,
        )
    except Exception as exc:
        return None, handler.ActionResponse.error(message=f'invalid event payload: {exc}')

    return envelope, None


def _build_run_create_binding(
    data: dict[str, Any],
    *,
    event: AgentEventEnvelope,
    run_id: str,
) -> tuple[AgentBinding | None, handler.ActionResponse | None]:
    binding_payload, error = _dict_payload(data.get('binding'), field_name='binding')
    if error:
        return None, error

    runner_id = binding_payload.get('runner_id') or data.get('runner_id')
    if not runner_id:
        return None, handler.ActionResponse.error(message='runner_id is required')

    scope_payload = binding_payload.get('scope')
    if scope_payload is None:
        agent_id = binding_payload.get('agent_id') or data.get('agent_id')
        workspace_id = event.workspace_id
        bot_id = event.bot_id
        if agent_id:
            scope_payload = {'scope_type': 'agent', 'scope_id': agent_id}
        elif bot_id:
            scope_payload = {'scope_type': 'bot', 'scope_id': bot_id}
        elif workspace_id:
            scope_payload = {'scope_type': 'workspace', 'scope_id': workspace_id}
        else:
            scope_payload = {'scope_type': 'global', 'scope_id': None}
    if not isinstance(scope_payload, dict):
        return None, handler.ActionResponse.error(message='binding.scope must be an object')

    runner_config_payload = binding_payload.get('runner_config', data.get('runner_config'))
    if runner_config_payload is None:
        runner_config_payload = {}
    if not isinstance(runner_config_payload, dict):
        return None, handler.ActionResponse.error(message='runner_config must be an object')

    resource_policy_payload = binding_payload.get('resource_policy', data.get('resource_policy'))
    if resource_policy_payload is None:
        resource_policy_payload = {}
    if not isinstance(resource_policy_payload, dict):
        return None, handler.ActionResponse.error(message='resource_policy must be an object')

    state_policy_payload = binding_payload.get('state_policy', data.get('state_policy'))
    if state_policy_payload is None:
        state_policy_payload = {}
    if not isinstance(state_policy_payload, dict):
        return None, handler.ActionResponse.error(message='state_policy must be an object')

    delivery_policy_payload = binding_payload.get('delivery_policy', data.get('delivery_policy'))
    if delivery_policy_payload is None:
        delivery_policy_payload = {
            'enable_streaming': bool(event.delivery.supports_streaming),
            'enable_reply': False,
        }
    if not isinstance(delivery_policy_payload, dict):
        return None, handler.ActionResponse.error(message='delivery_policy must be an object')

    try:
        binding = AgentBinding(
            binding_id=str(binding_payload.get('binding_id') or data.get('binding_id') or f'api:{runner_id}:{run_id}'),
            scope=BindingScope.model_validate(scope_payload),
            event_types=list(binding_payload.get('event_types') or data.get('event_types') or [event.event_type]),
            runner_id=str(runner_id),
            runner_config=runner_config_payload,
            resource_policy=ResourcePolicy.model_validate(resource_policy_payload),
            state_policy=StatePolicy.model_validate(state_policy_payload),
            delivery_policy=DeliveryPolicy.model_validate(delivery_policy_payload),
            enabled=bool(binding_payload.get('enabled', data.get('enabled', True))),
            agent_id=binding_payload.get('agent_id') or data.get('agent_id'),
        )
    except Exception as exc:
        return None, handler.ActionResponse.error(message=f'invalid binding payload: {exc}')

    if event.event_type not in binding.event_types:
        return None, handler.ActionResponse.error(
            message=f'binding.event_types must include event type {event.event_type}'
        )

    return binding, None


async def _consume_programmatic_run(
    h,
    *,
    run_id: str,
    event: AgentEventEnvelope,
    binding: AgentBinding,
    bound_plugins: list[str] | None,
) -> None:
    async for _result in h.ap.agent_run_orchestrator.run(
        event,
        binding,
        bound_plugins=bound_plugins,
        run_id=run_id,
    ):
        pass


def register(h):
    @h.action(_plugin_runtime_action('RUN_CREATE', 'run_create'))
    async def run_create(data: dict[str, Any]) -> handler.ActionResponse:
        """Create a programmatic AgentRunner run from an explicit event and binding."""
        caller_plugin_identity = data.get('caller_plugin_identity')
        if not _has_agent_runner_admin_permission(
            h.ap,
            caller_plugin_identity,
            AGENT_RUN_ADMIN_PERMISSION,
        ):
            return handler.ActionResponse.error(message='Run create access not authorized')

        orchestrator = getattr(h.ap, 'agent_run_orchestrator', None)
        if orchestrator is None:
            return handler.ActionResponse.error(message='AgentRunOrchestrator is not available')

        run_id = str(data.get('run_id') or uuid.uuid4())
        event, event_error = _build_run_create_event(data, run_id=run_id)
        if event_error:
            return event_error
        assert event is not None

        binding, binding_error = _build_run_create_binding(data, event=event, run_id=run_id)
        if binding_error:
            return binding_error
        assert binding is not None

        include_plugins = data.get('include_plugins')
        if include_plugins is not None and not isinstance(include_plugins, list):
            return handler.ActionResponse.error(message='include_plugins must be a list')
        bound_plugins = [str(item) for item in include_plugins] if include_plugins else None

        registry = getattr(h.ap, 'agent_runner_registry', None)
        if registry is not None:
            try:
                await registry.get(binding.runner_id, bound_plugins)
            except Exception as exc:
                return handler.ActionResponse.error(message=f'Runner {binding.runner_id} is not available: {exc}')

        async def background_run(*, raise_errors: bool = False) -> None:
            from ..agent.runner.run_ledger_store import RunLedgerStore

            store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())
            try:
                await _consume_programmatic_run(
                    h,
                    run_id=run_id,
                    event=event,
                    binding=binding,
                    bound_plugins=bound_plugins,
                )
            except Exception as exc:
                h.ap.logger.error(f'RUN_CREATE background run {run_id} failed: {exc}', exc_info=True)
                if await store.get_run(run_id) is None:
                    await store.create_run(
                        run_id=run_id,
                        event_id=event.event_id,
                        binding_id=binding.binding_id,
                        runner_id=binding.runner_id,
                        conversation_id=event.conversation_id,
                        thread_id=event.thread_id,
                        workspace_id=event.workspace_id,
                        bot_id=event.bot_id,
                        agent_id=binding.agent_id,
                        authorization={
                            'runner_id': binding.runner_id,
                            'binding_id': binding.binding_id,
                            'plugin_identity': None,
                            'resources': {},
                            'available_apis': {},
                            'conversation_id': event.conversation_id,
                            'bot_id': event.bot_id,
                            'workspace_id': event.workspace_id,
                            'thread_id': event.thread_id,
                        },
                        metadata={
                            'event_type': event.event_type,
                            'source': event.source,
                            'run_create_error': True,
                        },
                        status='running',
                    )
                await store.finalize_run(
                    run_id=run_id,
                    status='failed',
                    status_reason=str(exc),
                    metadata={'run_create_error': True},
                )
                if raise_errors:
                    raise

        if data.get('wait_for_completion'):
            try:
                await background_run(raise_errors=True)
            except Exception as exc:
                return handler.ActionResponse.error(message=f'Run create error: {exc}')
            from ..agent.runner.run_ledger_store import RunLedgerStore

            store = RunLedgerStore(h.ap.persistence_mgr.get_db_engine())
            run = await store.get_run(run_id)
            if run is not None:
                await _record_agent_runner_admin_action(
                    h.ap,
                    store,
                    action='run_create',
                    caller_plugin_identity=caller_plugin_identity,
                    permission=AGENT_RUN_ADMIN_PERMISSION,
                    durable_run_id=run_id,
                    detail={'runner_id': binding.runner_id, 'event_type': event.event_type},
                )
                return handler.ActionResponse.success(data=run)
        else:
            asyncio.create_task(background_run())

        await _record_agent_runner_admin_action(
            h.ap,
            None,
            action='run_create',
            caller_plugin_identity=caller_plugin_identity,
            permission=AGENT_RUN_ADMIN_PERMISSION,
            durable_run_id=run_id,
            detail={'runner_id': binding.runner_id, 'event_type': event.event_type},
        )
        return handler.ActionResponse.success(
            data={
                'run_id': run_id,
                'event_id': event.event_id,
                'agent_id': binding.agent_id,
                'binding_id': binding.binding_id,
                'runner_id': binding.runner_id,
                'conversation_id': event.conversation_id,
                'thread_id': event.thread_id,
                'workspace_id': event.workspace_id,
                'bot_id': event.bot_id,
                'status': 'created',
                'metadata': {
                    'event_type': event.event_type,
                    'source': event.source,
                    'accepted': True,
                },
            }
        )

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
