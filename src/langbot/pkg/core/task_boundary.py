from __future__ import annotations

import asyncio
import contextvars
import typing


T = typing.TypeVar('T')


def create_detached_task(
    coro: typing.Coroutine[typing.Any, typing.Any, T],
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    name: str | None = None,
    after_commit_manager: typing.Any | None = None,
) -> asyncio.Task[T]:
    """Create a task that inherits no request-local ContextVars.

    A normal ``asyncio.create_task`` copies the caller's context.  That is
    unsafe for work which outlives an HTTP request because it can copy the
    request's active database transaction or trusted tenant scope into a
    different asyncio task. Detached work must receive durable identity such
    as ``ExecutionContext`` through explicit arguments and establish its own
    tenant scope or unit of work whenever it accesses persistence.
    """

    task_loop = loop or asyncio.get_running_loop()
    gate: asyncio.Future[None] | None = None
    # Inspect the type so dynamic Mock/AsyncMock attributes do not turn into a
    # fake gate in lightweight tests or embedders.
    gate_factory = getattr(type(after_commit_manager), 'create_after_commit_gate', None)
    if callable(gate_factory):
        gate = gate_factory(after_commit_manager)
    task_coro = _wait_for_commit(coro, gate) if gate is not None else coro
    return task_loop.create_task(task_coro, name=name, context=contextvars.Context())


async def _wait_for_commit(
    coro: typing.Coroutine[typing.Any, typing.Any, T],
    gate: asyncio.Future[None],
) -> T:
    try:
        await gate
    except BaseException:
        coro.close()
        raise
    return await coro


async def run_in_workspace_uow(
    ap: typing.Any,
    workspace_uuid: str,
    operation: typing.Callable[[], typing.Awaitable[T]],
) -> T:
    """Run one short persistence section in a detached Cloud task scope.

    This helper deliberately scopes only the supplied operation.  Callers
    should not wrap long-running network or runtime work in a database
    transaction.
    """

    persistence_mgr = getattr(ap, 'persistence_mgr', None)
    if persistence_mgr is None:
        return await operation()
    cloud_runtime = getattr(getattr(persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
    if not cloud_runtime:
        return await operation()

    tenant_uow = getattr(persistence_mgr, 'tenant_uow', None)
    if not callable(tenant_uow):
        raise RuntimeError('Detached Cloud tasks require an explicit tenant unit of work')
    async with tenant_uow(workspace_uuid):
        return await operation()
