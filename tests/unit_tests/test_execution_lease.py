import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage, MonitoringError
from langbot.pkg.entity.persistence import workspace, user  # noqa: F401
from langbot.pkg.utils.execution_lease import reconcile_execution_leases


@pytest.mark.asyncio
async def test_host_lease_reaping_preserves_live_and_external_work():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    now = datetime.datetime(2026, 10, 10)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for name, owner, expiry, status, queue in (
            ('dead', 'dead-host', -1, 'running', None),
            ('other-tenant', 'dead-host', -1, 'running', None),
            ('ours', 'live-host', 30, 'running', None),
            ('other', 'other-host', 30, 'running', None),
            ('done', 'dead-host', -1, 'completed', None),
            ('legacy', None, None, 'running', None),
            ('remote', 'dead-host', -1, 'running', 'remote'),
        ):
            await conn.execute(sa.insert(AgentRun).values(
                run_id=name, runner_id='runner', workspace_id='other-workspace' if name == 'other-tenant' else 'workspace', status=status,
                queue_name=queue, execution_owner_id=owner,
                execution_lease_expires_at=now+datetime.timedelta(seconds=expiry) if expiry else None,
            ))
        await conn.execute(sa.insert(MonitoringMessage).values(
            id='pipeline', workspace_uuid='workspace', timestamp=now,
            bot_id='bot', bot_name='bot', pipeline_id='pipeline', pipeline_name='pipeline',
            message_content='hello', session_id='session', status='pending', level='info',
            execution_owner_id='dead-host', execution_lease_expires_at=now-datetime.timedelta(seconds=1),
        ))
    assert await reconcile_execution_leases(engine, 'workspace', now=now, owner_id='live-host') == 2
    assert await reconcile_execution_leases(engine, 'workspace', now=now, owner_id='live-host') == 0
    async with engine.connect() as conn:
        rows = {r['run_id']: r for r in (await conn.execute(sa.select(AgentRun))).mappings()}
        assert rows['dead']['status'] == 'failed'
        assert rows['dead']['status_reason']
        assert rows['dead']['finished_at'] == now
        assert rows['ours']['execution_lease_expires_at'] == now+datetime.timedelta(seconds=120)
        for key in ('ours', 'other', 'legacy', 'remote', 'other-tenant'):
            assert rows[key]['status'] == 'running'
        assert rows['done']['status'] == 'completed'
        assert (await conn.execute(sa.select(MonitoringMessage.status))).scalar_one() == 'error'
        assert (await conn.execute(sa.select(sa.func.count()).select_from(MonitoringError))).scalar_one() == 1
    await engine.dispose()

