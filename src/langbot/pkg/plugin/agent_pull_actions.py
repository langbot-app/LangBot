"""Agent-runner pull actions (history / event)."""

from __future__ import annotations

from typing import Any


from langbot_plugin.runtime.io import handler
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction,
)


from .agent_run_support import (
    _get_run_authorization,
    _validate_agent_run_session,
    _resolve_run_conversation,
    _run_scope_filters,
    _event_matches_run_scope,
    _project_event_record_for_api,
)


def register(h):
    @h.action(PluginToRuntimeAction.HISTORY_PAGE)
    async def history_page(data: dict[str, Any]) -> handler.ActionResponse:
        """Page through transcript history for a conversation.

        Requires run_id authorization. Only allows access to current run's conversation.
        """
        run_id = data.get('run_id')
        conversation_id = data.get('conversation_id')
        before_cursor = data.get('before_cursor')
        after_cursor = data.get('after_cursor')
        limit = data.get('limit', 50)
        direction = data.get('direction', 'backward')
        include_attachments = data.get('include_attachments', False)
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'History page',
            api_capability='history_page',
        )
        if error:
            return error

        conversation_id, scope_error = _resolve_run_conversation(
            session,
            conversation_id,
            'History page',
        )
        if scope_error:
            return scope_error

        if not conversation_id:
            return handler.ActionResponse.success(
                data={
                    'items': [],
                    'next_cursor': None,
                    'prev_cursor': None,
                    'has_more': False,
                }
            )

        # Parse cursors
        before_seq = int(before_cursor) if before_cursor else None
        after_seq = int(after_cursor) if after_cursor else None

        # Query transcript
        from ..agent.runner.transcript_store import TranscriptStore

        store = TranscriptStore(h.ap.persistence_mgr.get_db_engine())

        try:
            items, next_seq, prev_seq, has_more = await store.page_transcript(
                conversation_id=conversation_id,
                before_seq=before_seq,
                after_seq=after_seq,
                limit=limit,
                direction=direction,
                include_attachments=include_attachments,
                **_run_scope_filters(session),
            )

            return handler.ActionResponse.success(
                data={
                    'items': items,
                    'next_cursor': str(next_seq) if next_seq else None,
                    'prev_cursor': str(prev_seq) if prev_seq else None,
                    'has_more': has_more,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'HISTORY_PAGE error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'History page error: {e}')

    @h.action(PluginToRuntimeAction.HISTORY_SEARCH)
    async def history_search(data: dict[str, Any]) -> handler.ActionResponse:
        """Search transcript history.

        Requires run_id authorization. Only searches current run's conversation.
        Basic implementation using LIKE filtering.
        """
        run_id = data.get('run_id')
        query_text = data.get('query', '')
        filters = data.get('filters') or {}
        top_k = data.get('top_k', 10)
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'History search',
            api_capability='history_search',
        )
        if error:
            return error

        requested_conversation_id = filters.get('conversation_id')
        conversation_id, scope_error = _resolve_run_conversation(
            session,
            requested_conversation_id,
            'History search',
        )
        if scope_error:
            return scope_error

        if not conversation_id:
            return handler.ActionResponse.success(
                data={
                    'items': [],
                    'total_count': 0,
                    'query': query_text,
                }
            )

        # Search transcript
        from ..agent.runner.transcript_store import TranscriptStore

        store = TranscriptStore(h.ap.persistence_mgr.get_db_engine())

        try:
            safe_filters = {k: v for k, v in filters.items() if k != 'conversation_id'}
            items = await store.search_transcript(
                conversation_id=conversation_id,
                query_text=query_text,
                filters=safe_filters,
                top_k=top_k,
                **_run_scope_filters(session),
            )

            return handler.ActionResponse.success(
                data={
                    'items': items,
                    'total_count': len(items),
                    'query': query_text,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'HISTORY_SEARCH error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'History search error: {e}')

    @h.action(PluginToRuntimeAction.EVENT_GET)
    async def event_get(data: dict[str, Any]) -> handler.ActionResponse:
        """Get a single event record by ID.

        Requires run_id authorization. Only allows access to events in current run's conversation.
        """
        run_id = data.get('run_id')
        event_id = data.get('event_id')
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        if not event_id:
            return handler.ActionResponse.error(message='event_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Event get',
            api_capability='event_get',
        )
        if error:
            return error

        # Get event
        from ..agent.runner.event_log_store import EventLogStore

        store = EventLogStore(h.ap.persistence_mgr.get_db_engine())

        try:
            event = await store.get_event(event_id)
            if not event:
                return handler.ActionResponse.error(message=f'Event {event_id} not found')

            # Validate event is in the same conversation as the run, or was created by the same run.
            session_conversation_id = _get_run_authorization(session).get('conversation_id')
            event_run_id = event.get('run_id')
            if event_run_id and event_run_id == run_id:
                return handler.ActionResponse.success(data=_project_event_record_for_api(event))
            if not session_conversation_id or not _event_matches_run_scope(session, event):
                return handler.ActionResponse.error(message=f'Event {event_id} is not accessible by this run')

            return handler.ActionResponse.success(data=_project_event_record_for_api(event))
        except Exception as e:
            h.ap.logger.error(f'EVENT_GET error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Event get error: {e}')

    @h.action(PluginToRuntimeAction.EVENT_PAGE)
    async def event_page(data: dict[str, Any]) -> handler.ActionResponse:
        """Page through event records.

        Requires run_id authorization. Only allows access to current run's conversation.
        """
        run_id = data.get('run_id')
        conversation_id = data.get('conversation_id')
        event_types = data.get('event_types')
        before_cursor = data.get('before_cursor')
        limit = data.get('limit', 50)
        caller_plugin_identity = data.get('caller_plugin_identity')

        if not run_id:
            return handler.ActionResponse.error(message='run_id is required')

        session, error = await _validate_agent_run_session(
            run_id,
            caller_plugin_identity,
            h.ap,
            'Event page',
            api_capability='event_page',
        )
        if error:
            return error

        conversation_id, scope_error = _resolve_run_conversation(
            session,
            conversation_id,
            'Event page',
        )
        if scope_error:
            return scope_error

        if not conversation_id:
            return handler.ActionResponse.success(
                data={
                    'items': [],
                    'next_cursor': None,
                    'prev_cursor': None,
                    'has_more': False,
                }
            )

        # Parse cursor
        before_seq = int(before_cursor) if before_cursor else None

        # Query events
        from ..agent.runner.event_log_store import EventLogStore

        store = EventLogStore(h.ap.persistence_mgr.get_db_engine())

        try:
            items, next_seq, has_more = await store.page_events(
                conversation_id=conversation_id,
                event_types=event_types,
                before_seq=before_seq,
                limit=limit,
                **_run_scope_filters(session),
            )

            return handler.ActionResponse.success(
                data={
                    'items': [_project_event_record_for_api(item) for item in items],
                    'next_cursor': str(next_seq) if next_seq else None,
                    'prev_cursor': None,
                    'has_more': has_more,
                }
            )
        except Exception as e:
            h.ap.logger.error(f'EVENT_PAGE error: {e}', exc_info=True)
            return handler.ActionResponse.error(message=f'Event page error: {e}')
