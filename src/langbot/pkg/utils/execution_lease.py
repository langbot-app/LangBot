"""Host liveness leases; no age-based timeout for live executions.

Every leased execution row (a running ``agent_run`` or a pending
``monitoring_messages`` record) names its Host process (``execution_owner_id``)
and carries ``execution_lease_expires_at``. The owner renews its rows while it
is alive; anyone may mark rows whose lease expired as interrupted.

To keep maintenance proportional to in-flight work rather than to the number of
Workspaces, each Host first registers ``(owner, workspace)`` in the global
``execution_lease_scopes`` index before it writes a leased row there. A
maintenance tick then:

1. renews all of this Host's scopes with one statement;
2. renews its rows in each of its own scopes, reaps expired rows there, and
   drops scopes that no longer hold live work;
3. reaps a bounded batch of expired scopes (dead or stalled Hosts).

Nothing iterates over all Workspaces, so an instance with hundreds of
thousands of tenants costs the same as one with a handful.
"""

from __future__ import annotations

import asyncio
import datetime
import time
import typing
import uuid

import sqlalchemy as sa

from ..entity.persistence.agent_run import AgentRun
from ..entity.persistence.execution_lease import ExecutionLeaseScope
from ..entity.persistence.monitoring import MonitoringMessage, MonitoringError
from .inflight import inflight_hub

OWNER_ID = str(uuid.uuid4())
LEASE_SECONDS = 120
TICK_SECONDS = 20
# Own scopes must all be renewed every tick; a small fan-out bounds DB load.
OWN_SCOPE_CONCURRENCY = 4
# Expired scopes are rare (Host restarts or crashes); reap them in bounded batches.
EXPIRED_SCOPE_BATCH = 50
# Expired scopes this instance may not reap (another instance, fenced) are retried later.
FOREIGN_SCOPE_RETRY_SECONDS = 600
INTERRUPTED_REASON = 'Execution interrupted: the LangBot host stopped renewing its lease.'

# (owner, workspace) -> monotonic time of the last registration persisted / requested.
_scope_written_at: dict[tuple[str, str], float] = {}
_scope_used_at: dict[tuple[str, str], float] = {}


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def host_execution_lease():
    return {
        'execution_owner_id': OWNER_ID,
        'execution_lease_expires_at': _utc_now() + datetime.timedelta(seconds=LEASE_SECONDS),
    }


def _upsert_scope(dialect_name: str, owner_id: str, workspace_uuid: str, expires_at: datetime.datetime):
    values = {'owner_id': owner_id, 'workspace_uuid': workspace_uuid, 'expires_at': expires_at, 'generation': 0}
    if dialect_name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect_name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        return None
    statement = insert(ExecutionLeaseScope).values(**values)
    return statement.on_conflict_do_update(
        index_elements=[ExecutionLeaseScope.owner_id, ExecutionLeaseScope.workspace_uuid],
        set_={
            'expires_at': statement.excluded.expires_at,
            'generation': ExecutionLeaseScope.generation + 1,
        },
    )


async def register_execution_scope(engine, workspace_uuid: str | None, *, now=None, owner_id: str = OWNER_ID):
    """Record that ``owner_id`` is about to own leased rows in ``workspace_uuid``.

    Must complete before the leased row is written, so a crash can never leave a
    leased row that no scope points at. Repeated registrations within one tick
    are served from memory; the tick itself keeps the scope alive.
    """
    if not workspace_uuid:
        return
    key = (owner_id, workspace_uuid)
    clock = time.monotonic()
    _scope_used_at[key] = clock
    written_at = _scope_written_at.get(key)
    if written_at is not None and clock - written_at < TICK_SECONDS:
        return
    now = now or _utc_now()
    expires_at = now + datetime.timedelta(seconds=LEASE_SECONDS)
    async with engine.begin() as connection:
        statement = _upsert_scope(engine.dialect.name, owner_id, workspace_uuid, expires_at)
        if statement is not None:
            await connection.execute(statement)
        else:
            result = await connection.execute(
                sa.update(ExecutionLeaseScope)
                .where(ExecutionLeaseScope.owner_id == owner_id, ExecutionLeaseScope.workspace_uuid == workspace_uuid)
                .values(expires_at=expires_at, generation=ExecutionLeaseScope.generation + 1)
            )
            if not result.rowcount:
                await connection.execute(
                    sa.insert(ExecutionLeaseScope).values(
                        owner_id=owner_id, workspace_uuid=workspace_uuid, expires_at=expires_at, generation=0
                    )
                )
    _scope_written_at[key] = clock


def _forget_scope(key: tuple[str, str]) -> None:
    _scope_written_at.pop(key, None)
    _scope_used_at.pop(key, None)


async def _reconcile_workspace(engine, workspace_uuid, *, now, owner_id, live_owner_id=None):
    """Renew ``owner_id`` leases and reap expired rows in one Workspace.

    Returns ``(reaped_count, live_owned)`` where ``live_owned`` tells whether
    ``live_owner_id`` still holds unexpired leased rows in this Workspace.
    Never adopt a lease that already expired: another host may be reaping it.
    Remote queued/claimed runs and pre-upgrade rows without ownership are excluded.
    """
    changed = 0
    live_owned = False
    for model, statuses, scope, identity in (
        (AgentRun, ['running'], AgentRun.workspace_id, AgentRun.run_id),
        (MonitoringMessage, ['pending'], MonitoringMessage.workspace_uuid, MonitoringMessage.id),
    ):
        conditions = [model.status.in_(statuses), scope == workspace_uuid]
        if model is AgentRun:
            conditions.extend([AgentRun.queue_name.is_(None), AgentRun.claimed_by_runtime_id.is_(None)])
        async with engine.begin() as connection:
            if engine.dialect.name == 'postgresql':
                await connection.execute(
                    sa.text("SELECT set_config('langbot.workspace_uuid', :workspace, true)"),
                    {'workspace': workspace_uuid},
                )
            await connection.execute(
                sa.update(model)
                .where(
                    *conditions,
                    model.execution_owner_id == owner_id,
                    model.execution_lease_expires_at > now,
                )
                .values(execution_lease_expires_at=now + datetime.timedelta(seconds=LEASE_SECONDS))
            )
            expired = [*conditions, model.execution_lease_expires_at <= now]
            rows = (
                await connection.execute(
                    sa.select(identity).where(*expired).order_by(model.execution_lease_expires_at).limit(500)
                )
            ).all()
            if live_owner_id is not None and not live_owned:
                live_owned = (
                    await connection.execute(
                        sa.select(identity)
                        .where(
                            *conditions,
                            model.execution_owner_id == live_owner_id,
                            model.execution_lease_expires_at > now,
                        )
                        .limit(1)
                    )
                ).first() is not None
            if not rows:
                continue
            if model is MonitoringMessage:
                messages = (
                    (await connection.execute(sa.select(model).where(model.id.in_([row[0] for row in rows]))))
                    .mappings()
                    .all()
                )
                for message in messages:
                    result = await connection.execute(
                        sa.update(model)
                        .where(*expired, model.id == message['id'])
                        .values(status='error', level='error')
                    )
                    changed += result.rowcount
                    if result.rowcount:
                        await connection.execute(
                            sa.insert(MonitoringError).values(
                                id=str(uuid.uuid4()),
                                timestamp=now,
                                error_type='ExecutionInterrupted',
                                error_message=INTERRUPTED_REASON,
                                message_id=message['id'],
                                **{
                                    key: message[key]
                                    for key in (
                                        'workspace_uuid',
                                        'bot_id',
                                        'bot_name',
                                        'pipeline_id',
                                        'pipeline_name',
                                        'session_id',
                                    )
                                },
                            )
                        )
            else:
                result = await connection.execute(
                    sa.update(model)
                    .where(*expired, identity.in_([row[0] for row in rows]))
                    .values(status='failed', status_reason=INTERRUPTED_REASON, finished_at=now, updated_at=now)
                )
                changed += result.rowcount
            if len(rows) == 500:
                # More expired rows remain; keep the scope so the next tick continues.
                live_owned = True
    if changed:
        inflight_hub.notify(workspace_uuid)
    return changed, live_owned


async def reconcile_execution_leases(engine, workspace_uuid, *, now=None, owner_id=OWNER_ID):
    """Renew our live leases, then conditionally finish bounded expired batches."""
    now = now or _utc_now()
    changed, _ = await _reconcile_workspace(engine, workspace_uuid, now=now, owner_id=owner_id)
    return changed


async def _delete_scope(engine, owner_id, workspace_uuid, generation, *, expired_before=None) -> None:
    conditions = [
        ExecutionLeaseScope.owner_id == owner_id,
        ExecutionLeaseScope.workspace_uuid == workspace_uuid,
        ExecutionLeaseScope.generation == generation,
    ]
    if expired_before is not None:
        conditions.append(ExecutionLeaseScope.expires_at <= expired_before)
    async with engine.begin() as connection:
        await connection.execute(sa.delete(ExecutionLeaseScope).where(*conditions))


WorkspaceCheck = typing.Callable[[str], typing.Awaitable[str]]
"""Returns 'ok', 'gone' (Workspace no longer exists) or 'foreign' (not reapable here)."""


async def run_execution_lease_tick(
    engine,
    *,
    now=None,
    owner_id: str = OWNER_ID,
    check_workspace: WorkspaceCheck | None = None,
) -> int:
    """Run one maintenance pass; returns the number of executions marked interrupted."""
    now = now or _utc_now()
    renewed_until = now + datetime.timedelta(seconds=LEASE_SECONDS)
    Scope = ExecutionLeaseScope

    async with engine.begin() as connection:
        await connection.execute(
            sa.update(Scope).where(Scope.owner_id == owner_id, Scope.expires_at > now).values(expires_at=renewed_until)
        )
        own = (
            await connection.execute(
                sa.select(Scope.workspace_uuid, Scope.generation).where(
                    Scope.owner_id == owner_id, Scope.expires_at > now
                )
            )
        ).all()

    own_workspaces = {row[0] for row in own}
    for key in [key for key in _scope_written_at if key[0] == owner_id and key[1] not in own_workspaces]:
        # The scope was removed or expired behind our back; the next registration rewrites it.
        _scope_written_at.pop(key, None)
        if time.monotonic() - _scope_used_at.get(key, 0.0) >= LEASE_SECONDS:
            _scope_used_at.pop(key, None)

    total = 0
    semaphore = asyncio.Semaphore(OWN_SCOPE_CONCURRENCY)
    clock = time.monotonic()

    async def renew_own(workspace_uuid, generation):
        async with semaphore:
            changed, live = await _reconcile_workspace(
                engine, workspace_uuid, now=now, owner_id=owner_id, live_owner_id=owner_id
            )
            key = (owner_id, workspace_uuid)
            used_at = _scope_used_at.get(key)
            # A registration may precede its row insert; keep recently used scopes.
            if not live and (used_at is None or clock - used_at >= LEASE_SECONDS):
                await _delete_scope(engine, owner_id, workspace_uuid, generation)
                _forget_scope(key)
            return changed

    for changed in await asyncio.gather(*(renew_own(ws, generation) for ws, generation in own)):
        total += changed

    async with engine.begin() as connection:
        expired = (
            await connection.execute(
                sa.select(Scope.owner_id, Scope.workspace_uuid, Scope.generation)
                .where(Scope.expires_at <= now)
                .order_by(Scope.expires_at)
                .limit(EXPIRED_SCOPE_BATCH)
            )
        ).all()

    for dead_owner, workspace_uuid, generation in expired:
        state = await check_workspace(workspace_uuid) if check_workspace is not None else 'ok'
        if state == 'foreign':
            async with engine.begin() as connection:
                await connection.execute(
                    sa.update(Scope)
                    .where(
                        Scope.owner_id == dead_owner,
                        Scope.workspace_uuid == workspace_uuid,
                        Scope.generation == generation,
                        Scope.expires_at <= now,
                    )
                    .values(expires_at=now + datetime.timedelta(seconds=FOREIGN_SCOPE_RETRY_SECONDS))
                )
            continue
        live = False
        if state == 'ok':
            changed, live = await _reconcile_workspace(
                engine, workspace_uuid, now=now, owner_id=owner_id, live_owner_id=dead_owner
            )
            total += changed
        if not live:
            await _delete_scope(engine, dead_owner, workspace_uuid, generation, expired_before=now)
    return total


async def _check_workspace(ap, workspace_uuid: str) -> str:
    from ..workspace.errors import (
        WorkspaceExecutionUnavailableError,
        WorkspaceInvariantError,
        WorkspaceNotFoundError,
    )

    try:
        await ap.workspace_service.get_execution_binding(workspace_uuid)
    except WorkspaceNotFoundError:
        return 'gone'
    except (WorkspaceExecutionUnavailableError, WorkspaceInvariantError):
        return 'foreign'
    return 'ok'


async def maintain_execution_leases(ap):
    engine = ap.persistence_mgr.get_db_engine()
    while True:
        started = time.monotonic()
        try:
            count = await run_execution_lease_tick(
                engine, check_workspace=lambda workspace_uuid: _check_workspace(ap, workspace_uuid)
            )
            if count:
                ap.logger.info(f'Marked {count} interrupted executions as failed after host lease expiry')
        except Exception:
            ap.logger.exception('Execution lease maintenance failed')
        elapsed = time.monotonic() - started
        if elapsed > LEASE_SECONDS / 3:
            ap.logger.warning(f'Execution lease maintenance took {elapsed:.1f}s; leases expire after {LEASE_SECONDS}s')
        await asyncio.sleep(max(1.0, TICK_SECONDS - elapsed))
