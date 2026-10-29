"""Binding-local telemetry backed exclusively by the SDK Host storage API.

The plugin and its Page can be singletons: no tenant event, error, fence, or
initialization flag is retained in this object between invocations.
"""
import json
import logging

from components.shared_state import SerialState
from .telemetry import LangRAGTelemetry

logger = logging.getLogger(__name__)

KEY = 'langrag.telemetry.v1'
MAX_BYTES = 192 * 1024
MAX_EVENTS = 100


class InstallationTelemetry:
    start_timer = staticmethod(LangRAGTelemetry.start_timer)
    elapsed_ms = staticmethod(LangRAGTelemetry.elapsed_ms)
    new_trace_id = staticmethod(LangRAGTelemetry.new_trace_id)
    correlation_summary = staticmethod(LangRAGTelemetry.correlation_summary)

    def __init__(self, plugin):
        self.plugin = plugin
        self._state = SerialState()

    async def _transaction(self, operation):
        # Telemetry is installation-scoped, not knowledge-base-scoped.
        return await self._state.run(self.plugin, None, operation)

    async def initialize(self):
        """Process-scoped initialization cannot read tenant storage."""
        # The runtime dispatches installation revocation to the plugin instance,
        # which holds no back-reference to this helper; hand it the state so the
        # revocation hook can drop per-binding locks. Without the hook
        # (langbot-plugin 0.7.4) this attribute is simply never read.
        plugin = getattr(self, 'plugin', None)
        if plugin is not None:
            plugin.telemetry_serial_state = self._state

    async def _load(self):
        events = []
        if KEY in await self.plugin.get_plugin_storage_keys():
            raw = await self.plugin.get_plugin_storage(KEY)
            if len(raw) > MAX_BYTES:
                raise ValueError('Telemetry snapshot too large')
            events = json.loads(raw)
            if not isinstance(events, list) or len(events) > MAX_EVENTS:
                raise ValueError('Invalid telemetry snapshot')
        store = LangRAGTelemetry(max_history_events=MAX_EVENTS)
        for event in events:
            if not isinstance(event, dict) or not event.get('operation'):
                raise ValueError('Invalid telemetry event')
            store._record_event(event, persist=False)
        store._loaded_event_count = len(events)
        return store

    async def _persist(self, store):
        events = list(store._events)[-MAX_EVENTS:]
        while True:
            raw = json.dumps(events, ensure_ascii=False).encode()
            if len(raw) <= MAX_BYTES:
                break
            events.pop(0)
        try:
            await self.plugin.set_plugin_storage(KEY, raw)
        except BaseException as exc:
            # An interrupted (caller cancelled) or failed durable write leaves the
            # stored history unknown, so this diagnostic state fails closed from
            # here on. The marker stays in process: persisting it under the
            # installation-wide identity would fence every knowledge base of the
            # installation, including the ones this telemetry must never block.
            self._state.mark_fenced(self.plugin, None)
            if isinstance(exc, Exception):
                logger.warning('Could not persist LangRAG telemetry', exc_info=True)
            raise

    async def _record(self, method, kwargs):
        async def record():
            try:
                store = await self._load()
                getattr(store, method)(**kwargs)
                await self._persist(store)
            except Exception:
                # Diagnostic failure must not retry an acknowledged vector mutation.
                # No installation-specific error is retained on the singleton.
                pass
        await self._transaction(record)

    async def record_ingest(self, **kwargs):
        await self._record('record_ingest', kwargs)

    async def record_retrieval(self, **kwargs):
        await self._record('record_retrieval', kwargs)

    async def record_embedding_batch(self, **kwargs):
        await self._record('record_embedding_batch', kwargs)

    async def record_delete(self, **kwargs):
        await self._record('record_delete', kwargs)

    async def snapshot(self):
        return await self._transaction(self._snapshot)

    async def _snapshot(self):
        store = await self._load()
        result = store.snapshot()
        result['persistence'] = {
            'enabled': True, 'path': 'sdk:plugin-storage',
            'loaded_events': store._loaded_event_count,
            'history_events': len(store._events), 'error': None,
        }
        result['alerts'] = [a for a in result['alerts'] if a['code'] != 'persistence_disabled']
        result['health'] = store._health(result['alerts'])
        return result

    async def prometheus(self):
        return await self._transaction(self._prometheus)

    async def _prometheus(self):
        store = await self._load()
        return store.prometheus(await self._snapshot())

    async def clear(self):
        async def clear():
            try:
                await self.plugin.set_plugin_storage(KEY, b'[]')
            except BaseException as exc:
                # A clear that did not land cannot acknowledge deletion, so this
                # diagnostic state refuses further work from here on.
                self._state.mark_fenced(self.plugin, None)
                if isinstance(exc, Exception):
                    logger.warning('Could not clear LangRAG telemetry', exc_info=True)
                raise
        await self._transaction(clear)
