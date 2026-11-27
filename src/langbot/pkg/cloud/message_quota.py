"""Daily message reservations scoped to the signed Workspace entitlement."""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .entitlements import EntitlementUnavailableError
from .plan_policy import workspace_entitlement
from .quota_warning import maybe_schedule as schedule_quota_warning
from ..entity.persistence.workspace import WorkspaceMessageUsageDaily as Usage


def period_start():
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def daily_message_quota(ap, workspace_uuid, *, reserve=False):
    snapshot = await workspace_entitlement(ap, workspace_uuid)
    limit = snapshot.limits.get('messages.daily', 0) if snapshot else 0
    start = period_start()
    used = 0
    accepted = True
    if limit > 0:
        manager = ap.persistence_mgr
        read = sa.select(Usage.message_count).where(
            Usage.workspace_uuid == workspace_uuid, Usage.usage_date == start.date()
        )
        if reserve:
            insert = pg_insert if manager.get_db_engine().dialect.name == 'postgresql' else sqlite_insert
            statement = insert(Usage).values(workspace_uuid=workspace_uuid, usage_date=start.date(), message_count=1)
            statement = statement.on_conflict_do_update(
                index_elements=[Usage.workspace_uuid, Usage.usage_date],
                set_={'message_count': Usage.message_count + 1, 'updated_at': sa.func.now()},
                where=Usage.message_count < limit,
            ).returning(Usage.message_count)
            async with manager.tenant_write_uow(workspace_uuid, operation='message_quota.reserve') as uow:
                used = (await uow.execute(statement)).scalar_one_or_none()
                accepted = used is not None
                if not accepted:
                    used = (await uow.execute(read)).scalar_one()
                elif used == 1:
                    await uow.execute(
                        sa.delete(Usage).where(
                            Usage.workspace_uuid == workspace_uuid, Usage.usage_date < start.date() - timedelta(days=35)
                        )
                    )
            if accepted:
                schedule_quota_warning(ap, workspace_uuid, used=used, limit=limit, usage_date=start.date())
        else:
            async with manager.tenant_uow(workspace_uuid) as uow:
                used = (await uow.execute(read)).scalar_one_or_none() or 0
    return accepted, {
        'enforced': limit > 0,
        'limit': limit if limit > 0 else -1,
        'used': used,
        'remaining': max(0, limit - used) if limit > 0 else -1,
        'period': 'day',
        'timezone': 'UTC',
        'period_start': start.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'resets_at': (start + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


async def message_quota_status(ap, workspace_uuid):
    _, status = await daily_message_quota(ap, workspace_uuid)
    return status


async def message_quota_display(ap, workspace_uuid):
    """Quota for read-only Workspace summaries; None when the entitlement is unavailable."""
    try:
        return await message_quota_status(ap, workspace_uuid)
    except EntitlementUnavailableError:
        return None
