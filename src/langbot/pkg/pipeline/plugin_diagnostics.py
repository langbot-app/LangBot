from __future__ import annotations

import traceback
import weakref
from dataclasses import dataclass, field
from typing import Any

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message


@dataclass(frozen=True)
class PluginResponseSource:
    plugin: dict[str, str]
    event_name: str | None = None
    is_approximate: bool = False


@dataclass
class QueryDiagnosticState:
    pending_by_chain_id: dict[int, list[PluginResponseSource]] = field(default_factory=dict)
    by_response_index: dict[int, list[PluginResponseSource]] = field(default_factory=dict)
    finalizer: weakref.finalize | None = None


_QUERY_STATES: dict[int, QueryDiagnosticState] = {}


def record_plugin_response_source(
    query: pipeline_query.Query,
    response_index: int,
    response_sources: list[dict[str, Any]] | None,
    emitted_plugins: list[dict[str, Any]] | None = None,
    event_name: str | None = None,
) -> None:
    plugin_sources = _build_plugin_sources(response_sources, emitted_plugins, event_name)
    if not plugin_sources:
        return
    state = _get_or_create_query_state(query)
    state.by_response_index[response_index] = plugin_sources


def record_last_plugin_response_source(
    query: pipeline_query.Query,
    response_sources: list[dict[str, Any]] | None,
    emitted_plugins: list[dict[str, Any]] | None = None,
    event_name: str | None = None,
) -> None:
    record_plugin_response_source(
        query,
        len(query.resp_message_chain) - 1,
        response_sources,
        emitted_plugins,
        event_name,
    )


def record_pending_plugin_response_source(
    query: pipeline_query.Query,
    message_chain: platform_message.MessageChain,
    response_sources: list[dict[str, Any]] | None,
    emitted_plugins: list[dict[str, Any]] | None = None,
    event_name: str | None = None,
) -> None:
    plugin_sources = _build_plugin_sources(response_sources, emitted_plugins, event_name)
    if not plugin_sources:
        return
    state = _get_or_create_query_state(query)
    state.pending_by_chain_id[id(message_chain)] = plugin_sources


def consume_pending_plugin_response_source(
    query: pipeline_query.Query,
    message_chain: platform_message.MessageChain,
    response_index: int,
) -> None:
    state = _get_query_state(query)
    if state is None:
        return
    source = state.pending_by_chain_id.pop(id(message_chain), None)
    if source is None:
        return
    state.by_response_index[response_index] = source


def clear_response_source(query: pipeline_query.Query, response_index: int) -> None:
    state = _get_query_state(query)
    if state is None:
        return
    state.by_response_index.pop(response_index, None)
    _discard_query_state_if_empty(query)


async def notify_response_delivery_failure(
    ap: Any,
    query: pipeline_query.Query,
    response_index: int,
    message_chain: platform_message.MessageChain,
    error: Exception,
) -> None:
    try:
        plugin_refs = _get_response_sources(query, response_index)
        if not plugin_refs:
            return
        connector = getattr(ap, 'plugin_connector', None)
        if connector is None or not hasattr(connector, 'notify_plugin_diagnostic'):
            return
        for source in plugin_refs:
            payload = _build_delivery_failure_payload(
                plugin_ref=source.plugin,
                event_name=source.event_name,
                is_approximate=source.is_approximate,
                query=query,
                response_index=response_index,
                message_chain=message_chain,
                error=error,
            )
            try:
                await connector.notify_plugin_diagnostic(payload)
            except Exception as diag_error:
                _debug(ap, f'Plugin diagnostic forwarding failed: {diag_error}')
    except Exception as diag_error:
        _debug(ap, f'Plugin diagnostic forwarding skipped: {diag_error}')


def get_emitted_plugins(event_ctx: Any) -> list[dict[str, Any]]:
    emitted_plugins = getattr(event_ctx, '_emitted_plugins', [])
    return emitted_plugins if isinstance(emitted_plugins, list) else []


def get_response_sources(event_ctx: Any) -> list[dict[str, Any]] | None:
    event_attrs = vars(event_ctx)
    if '_response_sources' not in event_attrs:
        return None
    response_sources = event_attrs['_response_sources']
    return response_sources if isinstance(response_sources, list) else []


def _get_or_create_query_state(query: pipeline_query.Query) -> QueryDiagnosticState:
    query_key = id(query)
    state = _QUERY_STATES.get(query_key)
    if state is not None:
        return state

    state = QueryDiagnosticState()
    try:
        state.finalizer = weakref.finalize(query, _discard_query_state, query_key)
    except TypeError:
        state.finalizer = None
    _QUERY_STATES[query_key] = state
    return state


def _get_query_state(query: pipeline_query.Query) -> QueryDiagnosticState | None:
    return _QUERY_STATES.get(id(query))


def _discard_query_state(query_key: int) -> None:
    _QUERY_STATES.pop(query_key, None)


def _discard_query_state_if_empty(query: pipeline_query.Query) -> None:
    query_key = id(query)
    state = _QUERY_STATES.get(query_key)
    if state is None:
        return
    if state.pending_by_chain_id or state.by_response_index:
        return
    if state.finalizer is not None:
        state.finalizer.detach()
    _discard_query_state(query_key)


def _get_response_sources(
    query: pipeline_query.Query,
    response_index: int,
) -> list[PluginResponseSource]:
    state = _get_query_state(query)
    if state is None:
        return []
    return state.by_response_index.get(response_index, [])


def _extract_plugin_ref(plugin: Any) -> dict[str, str] | None:
    manifest = plugin.get('manifest') if isinstance(plugin, dict) else None
    metadata = manifest.get('metadata') if isinstance(manifest, dict) else None
    if not isinstance(metadata, dict):
        return None
    author = metadata.get('author')
    name = metadata.get('name')
    if not author or not name:
        return None
    return {'author': str(author), 'name': str(name)}


def _extract_response_source_plugin_ref(source: Any) -> dict[str, str] | None:
    if not isinstance(source, dict):
        return None
    if source.get('kind') != 'reply_message_chain':
        return None
    plugin_ref = source.get('plugin')
    if not isinstance(plugin_ref, dict):
        return None
    author = plugin_ref.get('author')
    name = plugin_ref.get('name')
    if not author or not name:
        return None
    return {'author': str(author), 'name': str(name)}


def _build_plugin_sources(
    response_sources: list[dict[str, Any]] | None,
    emitted_plugins: list[dict[str, Any]] | None,
    event_name: str | None,
) -> list[PluginResponseSource]:
    if response_sources is not None:
        plugin_refs = [_extract_response_source_plugin_ref(source) for source in response_sources]
        return [
            PluginResponseSource(plugin=plugin, event_name=event_name)
            for plugin in plugin_refs
            if plugin is not None
        ]

    if emitted_plugins:
        plugin_refs = [_extract_plugin_ref(plugin) for plugin in emitted_plugins]
        return [
            PluginResponseSource(plugin=plugin, event_name=event_name, is_approximate=True)
            for plugin in plugin_refs
            if plugin is not None
        ]
    return []


def _debug(ap: Any, message: str) -> None:
    logger = getattr(ap, 'logger', None)
    if logger is not None:
        logger.debug(message)


def _build_delivery_failure_payload(
    plugin_ref: dict[str, str],
    event_name: str | None,
    is_approximate: bool,
    query: pipeline_query.Query,
    response_index: int,
    message_chain: platform_message.MessageChain,
    error: Exception,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        'message_component_types': [component.__class__.__name__ for component in message_chain],
        'message_preview': str(message_chain)[:200],
    }
    if is_approximate:
        details['attribution_warning'] = (
            'This diagnostic was delivered to all plugins that handled the event because the '
            'plugin runtime did not report the exact reply_message_chain source.'
        )

    return {
        'level': 'ERROR',
        'code': 'response_delivery_failed',
        'message': 'Failed to deliver a plugin-provided response message.',
        'plugin': plugin_ref,
        'query': {
            'query_id': query.query_id,
            'event_name': event_name or query.message_event.__class__.__name__,
            'stage': query.current_stage_name or 'SendResponseBackStage',
            'response_index': response_index,
        },
        'details': details,
        'delivery': {
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'traceback': traceback.format_exception_only(type(error), error)[-1].strip(),
        },
    }
