"""Host liveness leases; no age-based timeout for live executions."""

import asyncio
import datetime
import uuid

import sqlalchemy as sa

from ..entity.persistence.agent_run import AgentRun
from ..entity.persistence.monitoring import MonitoringMessage, MonitoringError
from .inflight import inflight_hub

OWNER_ID = str(uuid.uuid4())
LEASE_SECONDS = 120
INTERRUPTED_REASON = 'Execution interrupted: the LangBot host stopped renewing its lease.'


def host_execution_lease():
    return {
        'execution_owner_id': OWNER_ID,
        'execution_lease_expires_at': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        + datetime.timedelta(seconds=LEASE_SECONDS),
    }


async def reconcile_execution_leases(engine, workspace_uuid, *, now=None, owner_id=OWNER_ID):
    """Renew our live leases, then conditionally finish bounded expired batches.

    Never adopt a lease that already expired: another host may be reaping it.
    Remote queued/claimed runs and pre-upgrade rows without ownership are excluded.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    changed = 0
    workspaces = set()
    for model, statuses, scope, identity in (
        (AgentRun, ['running'], AgentRun.workspace_id, AgentRun.run_id),
        (MonitoringMessage, ['pending'], MonitoringMessage.workspace_uuid, MonitoringMessage.id),
    ):
        conditions = [model.status.in_(statuses), scope == workspace_uuid]
        if model is AgentRun:
            conditions.extend([AgentRun.queue_name.is_(None), AgentRun.claimed_by_runtime_id.is_(None)])
        async with engine.begin() as connection:
            if engine.dialect.name == 'postgresql':
                await connection.execute(sa.text("SELECT set_config('langbot.workspace_uuid', :workspace, true)"),
                                         {'workspace': workspace_uuid})
            await connection.execute(sa.update(model).where(
                *conditions, model.execution_owner_id == owner_id,
                model.execution_lease_expires_at > now,
            ).values(execution_lease_expires_at=now + datetime.timedelta(seconds=LEASE_SECONDS)))
            expired = [*conditions, model.execution_lease_expires_at <= now]
            rows = (await connection.execute(sa.select(identity, scope).where(*expired)
                    .order_by(model.execution_lease_expires_at).limit(500))).all()
            if not rows:
                continue
            values = {'status': 'failed', 'status_reason': INTERRUPTED_REASON,
                      'finished_at': now, 'updated_at': now} if model is AgentRun else {
                          'status': 'error', 'level': 'error',
                      }
            if model is MonitoringMessage:
                messages = (await connection.execute(sa.select(model).where(
                    model.id.in_([row[0] for row in rows]),
                ))).mappings().all()
                for message in messages:
                    result = await connection.execute(sa.update(model).where(
                        *expired, model.id == message['id'],
                    ).values(**values))
                    changed += result.rowcount
                    if result.rowcount:
                        await connection.execute(sa.insert(MonitoringError).values(
                            id=str(uuid.uuid4()), timestamp=now,
                            error_type='ExecutionInterrupted', error_message=INTERRUPTED_REASON,
                            message_id=message['id'],
                            **{key: message[key] for key in (
                                'workspace_uuid', 'bot_id', 'bot_name', 'pipeline_id',
                                'pipeline_name', 'session_id',
                            )},
                        ))
            else:
                result = await connection.execute(sa.update(model).where(
                    *expired, identity.in_([row[0] for row in rows]),
                ).values(**values))
                changed += result.rowcount
            workspaces.update(row[1] for row in rows)
    for workspace in workspaces:
        inflight_hub.notify(workspace)
    return changed


async def maintain_execution_leases(ap):
    while True:
        try:
            count = 0
            for binding in await ap.workspace_service.list_active_execution_bindings():
                count += await reconcile_execution_leases(
                    ap.persistence_mgr.get_db_engine(), binding.workspace_uuid,
                )
            if count:
                ap.logger.info(f'Marked {count} interrupted executions as failed after host lease expiry')
        except Exception:
            ap.logger.exception('Execution lease maintenance failed')
        await asyncio.sleep(20)
