"""Installation- and knowledge-base-scoped state for LangRAG.

Locks and fences are keyed by ``(installation binding, knowledge-base identity)``
so an ambiguous failure for one knowledge base never blocks the other knowledge
bases that share the same installation. The platform storage key spans a whole
installation, so the knowledge-base id is always folded into our keys.

Only a dispatched mutation whose outcome is unknown fences: a validation error
raised before any call is dispatched, and ordinary cancellation before dispatch,
do not. A caller that goes away while its mutation is already in flight can
never observe the outcome, so that fences too, and it fences in the same step as
the cancellation so sibling operations fail closed instead of queueing behind
the unsettled mutation. A reply that does not say what happened to the rows is
an unknown outcome for the same reason. Fences are persisted (key includes the
knowledge-base identity) behind an in-process cache, so a restarted worker still
recognises them. A fence store that cannot be read refuses the operation rather
than assuming no fence.
"""
import asyncio
import hashlib
import inspect
import json
import logging
from functools import wraps
from weakref import WeakValueDictionary

logger = logging.getLogger(__name__)

FENCE_KEY_PREFIX = 'ke.fence.v1.'
# Fallback fence scope when the wrapped method carries no knowledge-base identity.
_INSTALLATION_FENCE_KEY = FENCE_KEY_PREFIX + 'installation'
_IDENTITY_ARGUMENTS = ('collection_id', 'kb_id', 'knowledge_base_id')


class AmbiguousMutationError(RuntimeError):
    """A dispatched mutation's outcome is unknown and requires reconciliation.

    Raise this from a call site when a mutation may have taken effect but its
    result is unknown. Only these failures fence a knowledge base.
    """


class FenceStateUnavailableError(RuntimeError):
    """Persisted fence records could not be read, so the fence state is unknown.

    An unreadable fence store must never be mistaken for "no fence": without
    this the plugin would mutate a knowledge base that may still be fenced. The
    read is not cached, so the operation is refused and retried later.
    """


async def settle(task):
    """Wait for a detached worker and return its result.

    Used by the bounded offload helper: a caller cancellation never abandons the
    thread that is already running, so the result is still awaited before the
    slot is released.
    """
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


async def _settle_commit(task, on_cancel=None):
    """Wait for a dispatched commit and report its outcome.

    Returns ``(caller_cancelled, failure)``; ``failure`` is the commit's
    exception, or ``asyncio.CancelledError`` when the commit itself was
    cancelled. Unlike :func:`settle` this never re-raises, because the caller has
    to fence an unknown outcome before propagating anything.

    ``on_cancel`` runs once, in the same step that observes the caller's first
    cancellation, so a fence can be raised before the detached commit settles.
    """
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if not cancelled and on_cancel is not None:
                on_cancel()
            cancelled = True
        except Exception:
            # The commit raised; its outcome is read from the state below.
            pass
    if task.cancelled():
        return cancelled, asyncio.CancelledError()
    return cancelled, task.exception()


def _kb_identity(method, instance, args, kwargs):
    """Extract the knowledge-base identity from a serialized method's arguments.

    Reads a ``collection_id`` / ``kb_id`` / ``knowledge_base_id`` argument first,
    then an argument exposing ``get_collection_id()`` or ``knowledge_base_id``
    (retrieval passes the whole context). Returns ``None`` when the wrapped
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
        getter = getattr(plugin, 'get_installation_binding', None)
        try:
            binding = getter() if getter else None
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
        return _kb_fence_key(kb_identity) in fenced or _INSTALLATION_FENCE_KEY in fenced

    async def _load_fences(self, plugin, binding):
        """Read persisted fences once per binding, failing closed on error.

        A failed read must never be mistaken for "no fence": the knowledge base
        stays unfenced in the cache, but this operation is refused so the caller
        retries instead of mutating a knowledge base whose fence state is
        unknown. ``CancelledError`` propagates unchanged, and the read is only
        marked done after it actually succeeded.
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
            raise FenceStateUnavailableError(
                f'Could not read persisted fences for {binding!r}: {exc!r}'
            ) from exc
        self._fence_loaded.add(binding)

    @staticmethod
    def _fenced_error(kb_identity):
        return RuntimeError(
            f'Knowledge base {kb_identity!r} fenced after an ambiguous mutation; '
            'reconcile before retrying'
        )

    async def run(self, plugin, kb_identity, operation, *, allow_fenced=False):
        binding = self.binding(plugin)
        # Refuse before queueing: a fence raised by an ambiguity that is still in
        # flight (a cancelled caller whose detached mutation may yet land) must
        # fail closed here instead of waiting behind the unsettled mutation.
        if not allow_fenced and self.is_fenced(binding, kb_identity):
            raise self._fenced_error(kb_identity)
        key = self._scope(binding, kb_identity)
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        async with lock:
            await self._load_fences(plugin, binding)
            if not allow_fenced and self.is_fenced(binding, kb_identity):
                raise self._fenced_error(kb_identity)
            try:
                return await operation()
            except AmbiguousMutationError:
                await self.fence(plugin, kb_identity, 'ambiguous mutation')
                raise

    async def mutate(self, plugin, kb_identity, operation, reason):
        """Run a mutation that was dispatched to the Host.

        A dispatched call whose outcome is unknown fences this knowledge base; a
        caller cancellation cancels the caller only after the dispatched call has
        settled, so the lock is never released over an unknown outcome. The
        caller that goes away can never observe that outcome, so the fence is
        raised in the same step as the cancellation: sibling operations fail
        closed instead of queueing behind an unsettled vector mutation.
        """
        binding = self.binding(plugin)
        fence_key = _kb_fence_key(kb_identity)
        task = asyncio.create_task(operation())
        cancelled, failure = await _settle_commit(
            task, on_cancel=lambda: self._fenced_keys(binding).add(fence_key)
        )
        if cancelled or failure is not None:
            await self.fence(
                plugin,
                kb_identity,
                reason if failure is None else f'{reason}: {failure!r}',
            )
        if cancelled:
            raise asyncio.CancelledError
        if failure is not None:
            raise failure
        return task.result()

    def mark_fenced(self, plugin, kb_identity):
        """Fence one knowledge base in process only, without touching storage.

        Used by diagnostics: a persisted marker written under the fallback
        identity is installation-wide, so it would fence every knowledge base
        that shares the installation and turn a telemetry write failure into a
        business-work outage. The in-process marker still makes the next
        operation of that component fail closed.
        """
        self._fenced_keys(self.binding(plugin)).add(_kb_fence_key(kb_identity))

    async def fence(self, plugin, kb_identity, reason):
        """Mark one knowledge base as requiring reconciliation.

        The in-process marker is set synchronously; persisting it is best effort
        so a caller cancellation cannot lose the fence.
        """
        fence_key = _kb_fence_key(kb_identity)
        self.mark_fenced(plugin, kb_identity)
        payload = json.dumps({'kb_id': kb_identity, 'reason': reason}).encode()
        cancelled, failure = await _settle_commit(
            asyncio.create_task(plugin.set_plugin_storage(fence_key, payload))
        )
        if failure is not None:
            logger.warning('Could not persist fence for %r: %r', kb_identity, failure)
        if cancelled:
            raise asyncio.CancelledError

    async def clear_fence(self, plugin, kb_identity):
        """Drop the fence for one knowledge base, in process and in storage.

        Used when a knowledge base is deleted: its pending ambiguity is moot, so
        deletion is the operator path out of a fence.
        """
        binding = self.binding(plugin)
        fence_key = _kb_fence_key(kb_identity)
        self._fenced_keys(binding).discard(fence_key)
        cancelled, failure = await _settle_commit(
            asyncio.create_task(plugin.set_plugin_storage(fence_key, b'null'))
        )
        if failure is not None:
            logger.warning('Could not clear fence for %r: %r', kb_identity, failure)
        if cancelled:
            raise asyncio.CancelledError

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
