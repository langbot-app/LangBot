"""PostgreSQL behavior of the Host execution lease scope registry."""

import datetime
import os

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence import user, workspace  # noqa: F401
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.execution_lease import ExecutionLeaseScope
from langbot.pkg.utils import execution_lease
from langbot.pkg.utils.execution_lease import LEASE_SECONDS, register_execution_scope, run_execution_lease_tick

pytestmark = [pytest.mark.integration, pytest.mark.slow]

NOW = datetime.datetime(2026, 11, 6, 5, 29, 54)


@pytest.fixture
async def engine():
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL not set')
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(sa.text('CREATE EXTENSION IF NOT EXISTS vector'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    execution_lease._scope_written_at.clear()
    execution_lease._scope_used_at.clear()
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_registration_upserts_and_dead_host_is_reaped(engine):
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='dead-host')
    execution_lease._scope_written_at.clear()
    await register_execution_scope(engine, 'workspace', now=NOW, owner_id='dead-host')
    async with engine.connect() as conn:
        row = (await conn.execute(sa.select(ExecutionLeaseScope))).one()
    assert (row.owner_id, row.workspace_uuid, row.generation) == ('dead-host', 'workspace', 1)

    async with engine.begin() as conn:
        await conn.execute(
            sa.insert(AgentRun).values(
                run_id='orphan',
                runner_id='runner',
                workspace_id='workspace',
                status='running',
                execution_owner_id='dead-host',
                execution_lease_expires_at=NOW + datetime.timedelta(seconds=LEASE_SECONDS),
            )
        )
    later = NOW + datetime.timedelta(seconds=LEASE_SECONDS + 1)
    assert await run_execution_lease_tick(engine, now=later, owner_id='live-host') == 1
    async with engine.connect() as conn:
        assert (await conn.execute(sa.select(AgentRun.status))).scalar_one() == 'failed'
        assert (await conn.execute(sa.select(sa.func.count()).select_from(ExecutionLeaseScope))).scalar_one() == 0
