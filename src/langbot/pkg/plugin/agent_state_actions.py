"""Agent-runner steering / state actions."""

from __future__ import annotations

from typing import Any


from langbot_plugin.runtime.io import handler
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction,
)


from ..agent.runner.session_registry import get_session_registry

from .agent_run_support import (
    _resolve_state_scope,
    _validate_agent_run_session,
)


def register(h):
    @h.action(PluginToRuntimeAction.STEERING_PULL)
    async def steering_pull(data: dict[str, Any]) -> handler.ActionResponse:
        """Pull pending steering/follow-up inputs for the current run."""
        run_id = data.get('run_id')
        mode = data.get('mode', 'all')
        limit = data.get('limit')
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        if limit is not None:
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                return handler.ActionResponse.error(message='limit must be an integer')
            if limit <= 0:
                return handler.ActionResponse.error(message='limit must be > 0')
            limit = min(limit, 100)

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Steering pull',
            api_capability='steering_pull',
        )
        if error:
            return error

        session_registry = get_session_registry()
        items = await session_registry.pull_steering(
            run_id,
            mode=str(mode or 'all'),
            limit=limit,
        )
        if items:
            try:
                from ..agent.runner.event_log_store import EventLogStore

                store = EventLogStore(h.ap.persistence_mgr.get_db_engine())
                for item in items:
                    event = item.get('event') if isinstance(item, dict) else None
                    conversation = item.get('conversation') if isinstance(item, dict) else None
                    actor = item.get('actor') if isinstance(item, dict) else None
                    subject = item.get('subject') if isinstance(item, dict) else None
                    if not isinstance(event, dict):
                        continue
                    await store.append_event(
                        event_id=None,
                        event_type='steering.injected',
                        source='agent_runner',
                        bot_id=conversation.get('bot_id') if isinstance(conversation, dict) else None,
                        workspace_id=conversation.get('workspace_id') if isinstance(conversation, dict) else None,
                        conversation_id=conversation.get('conversation_id') if isinstance(conversation, dict) else None,
                        thread_id=conversation.get('thread_id') if isinstance(conversation, dict) else None,
                        actor_type=actor.get('actor_type') if isinstance(actor, dict) else None,
                        actor_id=actor.get('actor_id') if isinstance(actor, dict) else None,
                        actor_name=actor.get('actor_name') if isinstance(actor, dict) else None,
                        subject_type=subject.get('subject_type') if isinstance(subject, dict) else None,
                        subject_id=subject.get('subject_id') if isinstance(subject, dict) else None,
                        input_summary=f'steering injected from {event.get("event_id")}',
                        run_id=run_id,
                        runner_id=session.get('runner_id') if isinstance(session, dict) else None,
                        metadata={
                            'steering': {
                                'status': 'injected',
                                'source_event_id': event.get('event_id'),
                                'claimed_by_run_id': item.get('claimed_run_id') if isinstance(item, dict) else run_id,
                                'claimed_runner_id': item.get('runner_id') if isinstance(item, dict) else None,
                                'claimed_at': item.get('claimed_at') if isinstance(item, dict) else None,
                                'pull_mode': str(mode or 'all'),
                            },
                        },
                    )
            except Exception as exc:
                h.ap.logger.warning(
                    f'Failed to write steering injection audit for run {run_id}: {exc}',
                    exc_info=True,
                )
        return handler.ActionResponse.success(data={'items': items})

    # ================= State APIs (run-scoped, policy-enforced) =================

    @h.action(PluginToRuntimeAction.STATE_GET)
    async def state_get(data: dict[str, Any]) -> handler.ActionResponse:
        """Get a state value from host-owned state store.

        Requires run_id authorization and scope enabled by state_policy.
        """
        run_id = data.get('run_id')
        scope = data.get('scope')
        key = data.get('key')
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        if not scope:
            return handler.ActionResponse.error(message='scope is required')

        if not key:
            return handler.ActionResponse.error(message='key is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'State get',
            api_capability='state',
        )
        if error:
            return error

        _state_context, scope_key, state_error = _resolve_state_scope(session, scope)
        if state_error:
            return state_error

        # Get state from persistent store
        from ..agent.runner.persistent_state_store import get_persistent_state_store

        store = get_persistent_state_store(h.ap.persistence_mgr.get_db_engine())

        try:
            value = await store.state_get(scope_key, key)
            return handler.ActionResponse.success(data={'value': value})
        except Exception as e:
            h.ap.logger.error(f'STATE_GET error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'State get error: {e}')

    @h.action(PluginToRuntimeAction.STATE_SET)
    async def state_set(data: dict[str, Any]) -> handler.ActionResponse:
        """Set a state value in host-owned state store.

        Requires run_id authorization and scope enabled by state_policy.
        Value must be JSON-serializable and size-limited.
        """
        run_id = data.get('run_id')
        scope = data.get('scope')
        key = data.get('key')
        value = data.get('value')
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        if not scope:
            return handler.ActionResponse.error(message='scope is required')

        if not key:
            return handler.ActionResponse.error(message='key is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'State set',
            api_capability='state',
        )
        if error:
            return error

        state_context, scope_key, state_error = _resolve_state_scope(session, scope)
        if state_error:
            return state_error

        # Get additional context for DB insert
        runner_id = session.get('runner_id', '')
        binding_identity = state_context.get('binding_identity', 'unknown')

        # Set state in persistent store
        from ..agent.runner.persistent_state_store import get_persistent_state_store

        store = get_persistent_state_store(h.ap.persistence_mgr.get_db_engine())

        try:
            success, error = await store.state_set(
                scope_key=scope_key,
                state_key=key,
                value=value,
                runner_id=runner_id,
                binding_identity=binding_identity,
                scope=scope,
                context=state_context,
                logger=h.ap.logger,
            )

            if not success:
                return handler.ActionResponse.error(message=error or 'Failed to set state')

            return handler.ActionResponse.success(data={'success': True})
        except Exception as e:
            h.ap.logger.error(f'STATE_SET error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'State set error: {e}')

    @h.action(PluginToRuntimeAction.STATE_DELETE)
    async def state_delete(data: dict[str, Any]) -> handler.ActionResponse:
        """Delete a state value from host-owned state store.

        Requires run_id authorization and scope enabled by state_policy.
        """
        run_id = data.get('run_id')
        scope = data.get('scope')
        key = data.get('key')
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        if not scope:
            return handler.ActionResponse.error(message='scope is required')

        if not key:
            return handler.ActionResponse.error(message='key is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'State delete',
            api_capability='state',
        )
        if error:
            return error

        _state_context, scope_key, state_error = _resolve_state_scope(session, scope)
        if state_error:
            return state_error

        # Delete state from persistent store
        from ..agent.runner.persistent_state_store import get_persistent_state_store

        store = get_persistent_state_store(h.ap.persistence_mgr.get_db_engine())

        try:
            deleted = await store.state_delete(scope_key, key)
            return handler.ActionResponse.success(data={'success': deleted})
        except Exception as e:
            h.ap.logger.error(f'STATE_DELETE error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'State delete error: {e}')

    @h.action(PluginToRuntimeAction.STATE_LIST)
    async def state_list(data: dict[str, Any]) -> handler.ActionResponse:
        """List state keys in a scope.

        Requires run_id authorization and scope enabled by state_policy.
        """
        run_id = data.get('run_id')
        scope = data.get('scope')
        prefix = data.get('prefix')
        limit = data.get('limit', 100)
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        if not scope:
            return handler.ActionResponse.error(message='scope is required')

        # Validate limit
        if not isinstance(limit, int) or limit <= 0:
            limit = 100
        limit = min(limit, 100)  # Cap at 100

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'State list',
            api_capability='state',
        )
        if error:
            return error

        _state_context, scope_key, state_error = _resolve_state_scope(session, scope)
        if state_error:
            return state_error

        # List state keys from persistent store
        from ..agent.runner.persistent_state_store import get_persistent_state_store

        store = get_persistent_state_store(h.ap.persistence_mgr.get_db_engine())

        try:
            keys, has_more = await store.state_list(scope_key, prefix, limit)
            return handler.ActionResponse.success(
                data={
                    'keys': keys,
                    'has_more': has_more,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'STATE_LIST error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'State list error: {e}')
