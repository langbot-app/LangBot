"""Installation- and memory-scope-scoped storage write lock and reconciliation fence.

One workspace installs this plugin once, and the same installation object graph is
reused by several product objects, so locks and fences are keyed by
``(installation binding, memory scope identity)``: an ambiguous failure for one
memory scope never blocks the other scopes that share the installation.

The identity is the dimension :class:`store.memory_store.MemoryStore` groups its
records by: ``scope_key`` for the L1 records (session/subject scope, see
``MemoryStore.get_scope_key``) and the collection id for the L2 episodes.  The
installation-wide ``kb_configs`` map carries no per-object identity, so it is
serialized on the installation scope instead.

Only a Host mutation that was dispatched with an unknown outcome fences a scope:
a deterministic error raised before the call, an error detected after the Host
answered authoritatively, and ordinary cancellation before dispatch do not.
Fences are persisted in installation-bound Host storage (the key folds in the
scope identity) behind an in-process cache, so a restarted worker still
recognises them, and process-local state is released when the installation is
revoked.
"""
import asyncio
import hashlib
import inspect
import json
import logging
from functools import wraps
from weakref import WeakValueDictionary

logger = logging.getLogger(__name__)

FENCE_KEY_PREFIX = "ke.fence.v1."
# Fallback fence scope for a write that carries no memory-scope identity.
_INSTALLATION_FENCE_KEY = FENCE_KEY_PREFIX + "installation"
# The arguments that carry the dimension MemoryStore groups records by, in
# priority order: the L1 scope_key first, then the L2 collection arguments.
_IDENTITY_ARGUMENTS = ("scope_key", "collection_id", "kb_id", "knowledge_base_id")


class AmbiguousMutationError(RuntimeError):
    """A dispatched Host mutation's outcome is unknown and requires reconciliation.

    Raise this from a serialized call site when a Host mutation may have taken
    effect but its result (or its durable record) is unknown and the call did not
    go through :meth:`BindingWrites.mutate`, which fences on its own. Only such
    failures fence a scope: deterministic errors raised before any Host call,
    errors detected after the Host answered authoritatively, and ordinary
    cancellation before dispatch do not.
    """


async def _settle_commit(task):
    """Wait for a dispatched Host commit and report its outcome.

    Repeated caller cancellation never abandons the wait, so a commit that was
    already dispatched settles before its scope lock is released. Returns
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
            # The commit raised; its outcome is read from the task below.
            pass
    if task.cancelled():
        return cancelled, asyncio.CancelledError()
    return cancelled, task.exception()


def _scope_identity(method, instance, args, kwargs):
    """Extract the memory-scope identity from a serialized method's arguments.

    Reads the ``scope_key`` the store groups L1 records by, then the collection
    arguments that group L2 episodes. Returns ``None`` when the wrapped method
    carries no identity, in which case the caller falls back to the
    installation-wide scope.
    """
    try:
        bound = inspect.signature(method).bind_partial(instance, *args, **kwargs)
    except (TypeError, ValueError):
        return None
    for name in _IDENTITY_ARGUMENTS:
        value = bound.arguments.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _fence_key(identity):
    if identity is None:
        return _INSTALLATION_FENCE_KEY
    return FENCE_KEY_PREFIX + hashlib.sha256(identity.encode()).hexdigest()


class BindingWrites:
    """Writes serialized per installation binding and memory scope."""

    def __init__(self):
        self._locks = WeakValueDictionary()
        # binding -> set of fence keys: an in-process cache in front of the
        # persisted markers, dropped wholesale when the installation is revoked.
        self._fenced = {}
        self._fence_loaded = set()
        # scope -> task holding that scope's lock, so a serialized write that
        # nests another serialized write for the same scope does not self-lock.
        self._owners = {}

    @staticmethod
    def binding(plugin):
        getter = getattr(plugin, 'get_installation_binding', None)
        try:
            binding = getter() if getter is not None else None
        except Exception:
            # Revocation has no invocation context; fall back to dedicated scope.
            binding = None
        return binding if binding is not None else ('dedicated',)

    @staticmethod
    def _scope(binding, identity):
        return (binding, identity)

    def _fenced_keys(self, binding):
        return self._fenced.setdefault(binding, set())

    def is_fenced(self, binding, identity):
        fenced = self._fenced.get(binding)
        if not fenced:
            return False
        return (
            _fence_key(identity) in fenced
            or _INSTALLATION_FENCE_KEY in fenced
        )

    async def _load_fences(self, plugin, binding):
        """Read persisted fences once per binding before allowing writes.

        An unavailable listing cannot establish that a restarted binding is
        safe. Refuse this write and retry the read on the next invocation.
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
                    # Unreadable marker: fail closed on whatever it fenced.
                    marker = {'reason': 'unreadable fence record'}
                if marker is not None:
                    fenced.add(key)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise RuntimeError(
                "Could not load persisted memory fences; retry after storage recovers"
            ) from exc
        self._fence_loaded.add(binding)

    async def run(self, plugin, identity, operation, *, allow_fenced=False):
        """Run one serialized write under its ``(installation, scope)`` lock.

        ``allow_fenced`` is for the operator actions that resolve a fence (the
        fenced object is deleted or rebuilt); every other write fails closed while
        the scope needs reconciliation.
        """
        binding = self.binding(plugin)
        scope = self._scope(binding, identity)
        task = asyncio.current_task()
        if self._owners.get(scope) is task:
            # Re-entrant call from inside this task's serialized write (for
            # example add_episode -> _auto_supersede): the lock is already held.
            return await operation()
        lock = self._locks.get(scope)
        if lock is None:
            lock = self._locks[scope] = asyncio.Lock()
        async with lock:
            await self._load_fences(plugin, binding)
            if not allow_fenced and self.is_fenced(binding, identity):
                raise RuntimeError(
                    f"Memory scope {identity if identity is not None else 'installation'!r} "
                    "fenced after an ambiguous Host mutation; reconciliation is required "
                    "before retrying"
                )
            self._owners[scope] = task
            try:
                return await operation()
            except AmbiguousMutationError:
                await self.fence(plugin, identity, 'ambiguous Host mutation')
                raise
            finally:
                self._owners.pop(scope, None)

    async def mutate(self, plugin, identity, operation, reason):
        """Run a mutation that was dispatched to the Host.

        A dispatched call whose outcome is unknown fences this memory scope; a
        caller cancellation cancels the caller only after the dispatched call has
        settled, so the lock is never released over an unknown outcome.
        """
        task = asyncio.create_task(operation())
        cancelled, failure = await _settle_commit(task)
        if failure is not None:
            await self.fence(plugin, identity, f'{reason}: {failure!r}')
        if cancelled:
            raise asyncio.CancelledError
        if failure is not None:
            raise failure
        return task.result()

    async def fence(self, plugin, identity, reason):
        """Mark one memory scope as requiring reconciliation.

        The in-process marker is set synchronously; persisting it to Host storage
        is best effort so that a caller cancellation cannot lose the fence.
        """
        binding = self.binding(plugin)
        fence_key = _fence_key(identity)
        self._fenced_keys(binding).add(fence_key)
        payload = json.dumps({
            'scope': identity if identity is not None else 'installation',
            'reason': reason,
        }).encode()
        cancelled, failure = await _settle_commit(
            asyncio.create_task(plugin.set_plugin_storage(fence_key, payload))
        )
        if failure is not None:
            logger.warning("Could not persist fence for %r: %r", identity, failure)
        if cancelled:
            raise asyncio.CancelledError

    async def clear_fence(self, plugin, identity):
        """Drop the fence for one memory scope, in process and in storage.

        Used when the fenced object is deleted or rebuilt: its pending ambiguity
        is moot, so acting on the object is the operator path out of a fence. A
        lingering persisted marker is inert because the tombstone is written.
        """
        binding = self.binding(plugin)
        fence_key = _fence_key(identity)
        fenced = self._fenced.get(binding)
        if fenced is not None:
            fenced.discard(fence_key)
            if not fenced:
                self._fenced.pop(binding, None)
        cancelled, failure = await _settle_commit(
            asyncio.create_task(plugin.set_plugin_storage(fence_key, b'null'))
        )
        if failure is not None:
            logger.warning("Could not clear fence for %r: %r", identity, failure)
        if cancelled:
            raise asyncio.CancelledError

    def release_binding(self, binding):
        """Drop process-local state keyed by one installation binding.

        The runtime hands one object graph to every installation of the artifact
        (shared by digest, never destroyed per installation), so a revoked
        installation's locks, owners and fence cache are only released here.
        """
        for scope in [item for item in self._locks if item[0] == binding]:
            self._locks.pop(scope, None)
        for scope in [item for item in self._owners if item[0] == binding]:
            self._owners.pop(scope, None)
        self._fenced.pop(binding, None)
        self._fence_loaded.discard(binding)


def serialized_write(method=None, *, scope=None, allow_fenced=False):
    """Serialize a store write under its ``(installation, memory scope)`` scope.

    ``scope`` may replace identity extraction with a ``(instance, args, kwargs)
    -> str | None`` callable, where ``None`` means the installation-wide scope
    (used by the single installation-wide record map). ``allow_fenced`` is for
    the operator actions that resolve a fence.
    """
    def decorate(func):
        @wraps(func)
        async def call(self, *args, **kwargs):
            identity = (
                scope(self, args, kwargs) if scope is not None
                else _scope_identity(func, self, args, kwargs)
            )
            return await self._writes.run(
                self.plugin,
                identity,
                lambda: func(self, *args, **kwargs),
                allow_fenced=allow_fenced,
            )
        return call

    return decorate if method is None else decorate(method)
