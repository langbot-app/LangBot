from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
import inspect
import types
import typing
import unittest.mock

from ..api.http.context import ExecutionContext
from ..workspace.errors import WorkspaceInvariantError


@dataclasses.dataclass
class ExecutionBindingLease:
    """Task-local, single-request execution binding validation state.

    Never shared across requests, never time-based (no TTL), and strictly
    invalidated whenever execution crosses an async suspension, untrusted
    stage, plugin RPC, database/adapter side effect, or active persistence
    transaction.
    """

    owner_task: asyncio.Task[typing.Any] | None
    workspace_service: typing.Any = None
    instance_uuid: str = ''
    workspace_uuid: str = ''
    placement_generation: int = 0
    instance_verified: bool = False
    valid: bool = False

    def matches(
        self,
        workspace_service: typing.Any,
        execution_context: ExecutionContext,
        *,
        require_instance_match: bool,
    ) -> bool:
        if not self.valid:
            return False
        if self.owner_task is not _current_task():
            return False
        if self.workspace_service is not workspace_service:
            return False
        if require_instance_match and not self.instance_verified:
            return False
        return (
            self.instance_uuid == execution_context.instance_uuid
            and self.workspace_uuid == execution_context.workspace_uuid
            and self.placement_generation == execution_context.placement_generation
        )

    def mark_valid(
        self,
        workspace_service: typing.Any,
        execution_context: ExecutionContext,
        *,
        instance_verified: bool,
    ) -> None:
        if self.owner_task is not _current_task():
            return
        self.workspace_service = workspace_service
        self.instance_uuid = execution_context.instance_uuid
        self.workspace_uuid = execution_context.workspace_uuid
        self.placement_generation = execution_context.placement_generation
        self.instance_verified = instance_verified
        self.valid = True

    def invalidate(self) -> None:
        self.valid = False
        self.instance_verified = False
        self.workspace_service = None


_ACTIVE_LEASE: contextvars.ContextVar[ExecutionBindingLease | None] = contextvars.ContextVar(
    'langbot_pipeline_execution_binding_lease',
    default=None,
)


def _current_task() -> asyncio.Task[typing.Any] | None:
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


def _active_same_task_lease() -> ExecutionBindingLease | None:
    lease = _ACTIVE_LEASE.get()
    if lease is None:
        return None
    if lease.owner_task is not _current_task():
        return None
    return lease


def _has_active_persistence_session(ap: typing.Any) -> bool:
    """Return True when a task-bound SQLAlchemy session is active.

    When callers hold an open Session, uncommitted ORM changes to Workspace
    fencing or placement generation must take effect immediately, so we never
    reuse a lease inside an active Session.
    """
    persistence_mgr = getattr(ap, 'persistence_mgr', None)
    if persistence_mgr is None or isinstance(persistence_mgr, unittest.mock.NonCallableMock):
        return False
    current_session = getattr(persistence_mgr, 'current_session', None)
    if not callable(current_session) or inspect.iscoroutinefunction(current_session):
        return False
    session = current_session()
    if inspect.isawaitable(session):
        close = getattr(session, 'close', None)
        if callable(close):
            close()
        return True
    return session is not None


@contextlib.contextmanager
def execution_binding_scope() -> typing.Iterator[ExecutionBindingLease]:
    """Open a fresh per-request execution binding lease scope for this task."""
    lease = ExecutionBindingLease(owner_task=_current_task())
    token = _ACTIVE_LEASE.set(lease)
    try:
        yield lease
    finally:
        lease.invalidate()
        _ACTIVE_LEASE.reset(token)


@contextlib.contextmanager
def ensure_execution_binding_scope() -> typing.Iterator[ExecutionBindingLease]:
    """Reuse an active same-task scope or open a fresh one for standalone calls."""
    existing = _active_same_task_lease()
    if existing is not None:
        yield existing
        return
    with execution_binding_scope() as lease:
        yield lease


def invalidate_execution_binding_lease() -> None:
    """Invalidate the current task's active execution binding lease, if any."""
    lease = _active_same_task_lease()
    if lease is not None:
        lease.invalidate()


async def ensure_execution_binding_active(
    ap: typing.Any,
    execution_context: ExecutionContext,
    *,
    require_instance_match: bool = True,
    instance_mismatch_message: str = 'Execution instance does not match the active Workspace binding',
    force: bool = False,
) -> ExecutionContext:
    """Validate Workspace execution binding, reusing a same-segment lease when safe."""
    workspace_service = ap.workspace_service
    in_session = _has_active_persistence_session(ap)
    lease = _active_same_task_lease()

    if (
        not force
        and not in_session
        and lease is not None
        and lease.matches(
            workspace_service,
            execution_context,
            require_instance_match=require_instance_match,
        )
    ):
        return execution_context

    if lease is not None:
        lease.invalidate()

    binding = await workspace_service.get_execution_binding(
        execution_context.workspace_uuid,
        expected_generation=execution_context.placement_generation,
    )
    if require_instance_match and binding.instance_uuid != execution_context.instance_uuid:
        raise WorkspaceInvariantError(instance_mismatch_message)

    if lease is not None and not _has_active_persistence_session(ap):
        lease.mark_valid(
            workspace_service,
            execution_context,
            instance_verified=require_instance_match,
        )
    return execution_context


@types.coroutine
def _yield_future(value: typing.Any) -> typing.Generator[typing.Any, typing.Any, typing.Any]:
    return (yield value)


async def _drive_after_first_yield(awaitable: typing.Any, first_yielded: typing.Any) -> typing.Any:
    yielded = first_yielded
    try:
        while True:
            try:
                sent = await _yield_future(yielded)
            except BaseException as exc:
                try:
                    yielded = awaitable.throw(exc)
                except StopIteration as done:
                    return done.value
            else:
                try:
                    yielded = awaitable.send(sent)
                except StopIteration as done:
                    return done.value
    finally:
        close = getattr(awaitable, 'close', None)
        if callable(close):
            close()


async def await_tracking_suspension(awaitable: typing.Any) -> tuple[typing.Any, bool]:
    """Await a coroutine and report whether it suspended to the event loop."""
    if not (inspect.iscoroutine(awaitable) or hasattr(awaitable, 'send')):
        return await awaitable, True
    try:
        first_yielded = awaitable.send(None)
    except StopIteration as done:
        return done.value, False
    return await _drive_after_first_yield(awaitable, first_yielded), True


async def anext_tracking_suspension(
    iterator: typing.AsyncIterator[typing.Any],
) -> tuple[bool, typing.Any, bool]:
    """Advance an async iterator and report (has_item, item, suspended)."""
    step = iterator.__anext__()
    if not (inspect.iscoroutine(step) or hasattr(step, 'send')):
        try:
            return True, await step, True
        except StopAsyncIteration:
            return False, None, True
    try:
        first_yielded = step.send(None)
    except StopIteration as done:
        return True, done.value, False
    except StopAsyncIteration:
        return False, None, False
    try:
        value = await _drive_after_first_yield(step, first_yielded)
    except StopAsyncIteration:
        return False, None, True
    return True, value, True
