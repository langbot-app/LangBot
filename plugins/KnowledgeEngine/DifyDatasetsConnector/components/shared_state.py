"""Installation- and knowledge-base-scoped state using the SDK-bound Host proxy.

Bundled in each independent archive. No filesystem/global tenant registry.

Locks and fences are keyed by ``(installation binding, knowledge-base identity)``
so an ambiguous failure for one knowledge base never blocks the other knowledge
bases that share the same installation; the platform storage key is the same for
a whole installation, hence the knowledge-base id is always folded into our keys.
Fences are persisted in installation-bound Host storage (key includes the
knowledge-base id) with an in-process cache in front, so a restarted worker still
recognises them. Only dispatched mutations whose outcome is unknown fence; a
deterministic validation error raised before any remote call and ordinary
cancellation before a call is dispatched do not.
"""
import asyncio
import hashlib
import inspect
import json
import logging
from functools import wraps
from contextlib import asynccontextmanager
import httpx
from weakref import WeakValueDictionary

logger = logging.getLogger(__name__)

HTTP_TOTAL_TIMEOUT = 150.0
FENCE_KEY_PREFIX = "ke.fence.v1."
# Fallback fence scope when the wrapped method carries no knowledge-base identity.
_INSTALLATION_FENCE_KEY = FENCE_KEY_PREFIX + "installation"
_IDENTITY_ARGUMENTS = ('kb_id', 'collection_id', 'knowledge_base_id')


class AmbiguousMutationError(RuntimeError):
    """A dispatched mutation's outcome is unknown and requires reconciliation.

    Raise this from a call site when a remote mutation may have taken effect but
    its result (or its durable record) is unknown. Only these failures fence a
    knowledge base; deterministic errors raised before any remote call, and
    ordinary cancellation before a call is dispatched, do not fence.
    """


class FenceStateUnavailableError(RuntimeError):
    """Persisted fence state could not be read, so the fence cannot be confirmed.

    A failed read is not evidence that no fence exists, so the operation fails
    closed rather than proceeding as if the knowledge base were clear. The read
    is retried on the next call instead of being cached as loaded.
    """


def is_ambiguous_http_failure(exc):
    """Whether a failed provider call had an unknown outcome.

    A response status means the provider answered, so the failure is
    deterministic. A connection that was never established means nothing was
    dispatched. Everything else (timeout, lost connection, unparsable response)
    was dispatched with an unknown outcome.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return False
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return False
    return True


async def _settle_commit(task):
    """Wait for a dispatched commit and report its outcome.

    Repeated caller cancellation never abandons the wait, so a Host commit that
    was already dispatched settles before its lock is released. Returns
    ``(caller_cancelled, failure)``; ``failure`` is the commit's exception, or
    ``asyncio.CancelledError`` when the commit itself was cancelled.
    """
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            # The commit raised; its outcome is read from the state below.
            pass
    if task.cancelled():
        return cancelled, asyncio.CancelledError()
    return cancelled, task.exception()


def _kb_identity(method, instance, args, kwargs):
    """Extract the knowledge-base identity from a serialized method's arguments.

    Reads a ``kb_id`` / ``collection_id`` / ``knowledge_base_id`` argument first,
    then an argument exposing ``get_collection_id()`` or ``knowledge_base_id``
    (ingestion passes the whole context). Returns ``None`` when the wrapped
    method carries no knowledge-base identity, in which case the caller falls
    back to an installation-wide lock and fence.
    """
    try:
        bound = inspect.signature(method).bind_partial(instance, *args, **kwargs)
    except (TypeError, ValueError):
        return None
    for name in _IDENTITY_ARGUMENTS:
        value = bound.arguments.get(name)
        if isinstance(value, str) and value:
            return value
    for value in bound.arguments.values():
        getter = getattr(value, 'get_collection_id', None)
        if callable(getter):
            try:
                identity = getter()
            except Exception:
                continue
            if isinstance(identity, str) and identity:
                return identity
        identity = getattr(value, 'knowledge_base_id', None)
        if isinstance(identity, str) and identity:
            return identity
    return None


def _kb_fence_key(kb_identity):
    if kb_identity is None:
        return _INSTALLATION_FENCE_KEY
    return FENCE_KEY_PREFIX + hashlib.sha256(kb_identity.encode()).hexdigest()


class SerialState:
    def __init__(self):
        self._locks = WeakValueDictionary()
        # binding -> set of fence keys; cache in front of persisted fences.
        self._fenced = {}
        self._fence_loaded = set()

    @staticmethod
    def binding(plugin):
        try:
            binding = plugin.get_installation_binding()
        except Exception:
            # Revocation has no invocation context; fall back to dedicated scope.
            binding = None
        return binding if binding is not None else ('dedicated',)

    @staticmethod
    def _scope(binding, kb_identity):
        return (binding, kb_identity)

    def _fenced_keys(self, binding):
        return self._fenced.setdefault(binding, set())

    def is_fenced(self, binding, kb_identity):
        fenced = self._fenced_keys(binding)
        return (
            _kb_fence_key(kb_identity) in fenced
            or _INSTALLATION_FENCE_KEY in fenced
        )

    async def _load_fences(self, plugin, binding):
        """Read persisted fences once per binding.

        A failed read cannot be treated as "no fence": it means the fence state
        is unknown, so the caller fails closed and retries on the next call
        rather than caching the failure as loaded.
        """
        if binding in self._fence_loaded:
            return
        try:
            keys = await plugin.get_plugin_storage_keys()
            fenced = self._fenced_keys(binding)
            for key in keys:
                if not key.startswith(FENCE_KEY_PREFIX):
                    continue
                try:
                    marker = json.loads(await plugin.get_plugin_storage(key))
                except Exception:
                    # Unreadable marker: fail closed on this knowledge base.
                    marker = {'reason': 'unreadable fence record'}
                if marker is not None:
                    fenced.add(key)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Could not read persisted fences for %r", binding, exc_info=True)
            raise FenceStateUnavailableError(
                f"Could not confirm persisted fence state for {binding!r}: {exc!r}"
            ) from exc
        self._fence_loaded.add(binding)

    async def run(self, plugin, kb_identity, operation, *, allow_fenced=False):
        binding = self.binding(plugin)
        key = self._scope(binding, kb_identity)
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        async with lock:
            await self._load_fences(plugin, binding)
            if not allow_fenced and self.is_fenced(binding, kb_identity):
                raise RuntimeError(
                    f"Knowledge base {kb_identity!r} fenced after an ambiguous mutation; "
                    "reconcile with the provider before retrying"
                )
            try:
                return await operation()
            except AmbiguousMutationError:
                await self.fence(plugin, kb_identity, 'ambiguous remote mutation')
                raise

    async def dispatched(self, plugin, kb_identity, operation, reason):
        """Dispatch a remote mutation under a pre-persisted intent.

        The fence is written before the request goes out, so a cancellation after
        dispatch (or an ambiguous failure) cannot leave a mutation with no marker
        for reconciliation; a deterministic answer clears it again.
        """
        await self.fence(plugin, kb_identity, reason)
        try:
            result = await operation()
        except asyncio.CancelledError:
            # Dispatched, outcome unknown: keep the fence and let the caller see it.
            raise
        except Exception as exc:
            if not is_ambiguous_http_failure(exc):
                await self.clear_fence(plugin, kb_identity)
            raise
        await self.clear_fence(plugin, kb_identity)
        return result

    async def fence(self, plugin, kb_identity, reason):
        """Mark one knowledge base as requiring reconciliation.

        The in-process marker is set synchronously; persisting it to Host storage
        is best effort so that a caller cancellation cannot lose the fence.
        """
        binding = self.binding(plugin)
        fence_key = _kb_fence_key(kb_identity)
        self._fenced_keys(binding).add(fence_key)
        payload = json.dumps({'kb_id': kb_identity, 'reason': reason}).encode()
        cancelled, failure = await _settle_commit(
            asyncio.create_task(plugin.set_plugin_storage(fence_key, payload))
        )
        if failure is not None:
            logger.warning("Could not persist fence for %r: %r", kb_identity, failure)
        if cancelled:
            raise asyncio.CancelledError

    async def clear_fence(self, plugin, kb_identity):
        """Drop the fence for one knowledge base, in process and in storage.

        Used when a knowledge base is deleted: its pending ambiguity is moot, so
        the operator path out of a fence is deletion. A lingering persisted
        marker is inert because the configuration tombstone is already written.
        """
        binding = self.binding(plugin)
        fence_key = _kb_fence_key(kb_identity)
        self._fenced_keys(binding).discard(fence_key)
        cancelled, failure = await _settle_commit(
            asyncio.create_task(plugin.set_plugin_storage(fence_key, b'null'))
        )
        if failure is not None:
            logger.warning("Could not clear fence for %r: %r", kb_identity, failure)
        if cancelled:
            raise asyncio.CancelledError

    async def write(self, plugin, kb_identity, key, value):
        # A caller cancellation must not abandon a dispatched Host commit while
        # its lock is released; settle it and fence only a real ambiguity.
        task = asyncio.create_task(plugin.set_plugin_storage(key, value))
        cancelled, failure = await _settle_commit(task)
        if failure is not None:
            await self.fence(plugin, kb_identity, f'Host write outcome unknown: {failure!r}')
        if cancelled:
            raise asyncio.CancelledError
        if failure is not None:
            raise failure
        return task.result()

    def release_binding(self, binding):
        """Drop process-local state keyed by one installation binding."""
        for key in [k for k in self._locks if k[0] == binding]:
            self._locks.pop(key, None)
        self._fenced.pop(binding, None)
        self._fence_loaded.discard(binding)


def serialized(method=None, *, allow_fenced=False):
    def decorate(func):
        @wraps(func)
        async def call(self, *args, **kwargs):
            return await self._state.run(
                self.plugin,
                _kb_identity(func, self, args, kwargs),
                lambda: func(self, *args, **kwargs),
                allow_fenced=allow_fenced,
            )
        return call
    return decorate if method is None else decorate(method)


class ConfigStore:
    """No credential cache: every delete resolves durable installation storage.

    A JSON null tombstone makes missing KBs explicit without ambiguous delete RPCs.
    The one mutation lock also orders ingest/delete/create inside this worker.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = SerialState()
        self._http_slots = asyncio.Semaphore(4)

    async def initialize(self) -> None:
        await super().initialize()
        # The runtime dispatches installation revocation to the plugin instance,
        # which holds no back-reference to its components; hand it this
        # component's state so the revocation hook can drop per-binding locks and
        # fences. Without the hook (langbot-plugin 0.7.4) this attribute is simply
        # never read.
        plugin = getattr(self, 'plugin', None)
        if plugin is not None:
            plugin.knowledge_engine_serial_state = self._state

    @asynccontextmanager
    async def http_client(self):
        # Include queueing and the whole response body in the deadline, not just
        # individual socket reads. Clients/credentials never survive a call.
        async with asyncio.timeout(HTTP_TOTAL_TIMEOUT):
            async with self._http_slots:
                async with httpx.AsyncClient() as client:
                    yield client

    @staticmethod
    def _key(kb_id):
        return "ke.config.v1." + hashlib.sha256(kb_id.encode()).hexdigest()

    async def _save_config(self, kb_id, config):
        value = json.dumps(config, ensure_ascii=False).encode()
        if len(value) > 65536:
            raise ValueError("Knowledge-base configuration exceeds 64 KiB")
        await self._state.write(self.plugin, kb_id, self._key(kb_id), value)

    async def _load_config(self, kb_id):
        key = self._key(kb_id)
        # Only an authoritative keys response establishes absence; RPC errors propagate.
        if key not in await self.plugin.get_plugin_storage_keys():
            return None
        value = json.loads(await self.plugin.get_plugin_storage(key))
        if value is not None and not isinstance(value, dict):
            raise ValueError("Invalid persisted knowledge-base configuration")
        return value

    @staticmethod
    def _document_key(kb_id, host_document_id):
        return "ke.document.v1." + hashlib.sha256(
            json.dumps([kb_id, host_document_id]).encode()
        ).hexdigest()

    async def _load_document(self, kb_id, host_document_id):
        key = self._document_key(kb_id, host_document_id)
        keys = await self.plugin.get_plugin_storage_keys()
        if key in keys:
            value = json.loads(await self.plugin.get_plugin_storage(key))
        else:
            # Current Host passes the durable upstream ID on delete; older Host
            # revisions pass its file UUID. Resolve either without trusting an
            # arbitrary unrecorded identifier.
            matches = []
            for candidate in keys:
                if candidate.startswith('ke.document.v1.'):
                    item = json.loads(await self.plugin.get_plugin_storage(candidate))
                    if item.get('kb_id') == kb_id and item.get('upstream_id') == host_document_id:
                        matches.append(item)
            if len(matches) > 1:
                raise ValueError('Ambiguous upstream document ID')
            return matches[0] if matches else None
        if not isinstance(value, dict) or not isinstance(value.get('upstream_id'), str):
            raise ValueError('Invalid upstream document mapping; reconcile installation')
        return value

    async def _save_document(self, kb_id, host_document_id, value):
        value = {**value, 'kb_id': kb_id, 'host_document_id': host_document_id}
        await self._state.write(self.plugin, kb_id, self._document_key(kb_id, host_document_id),
                                json.dumps(value).encode())
