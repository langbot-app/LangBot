from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import TenantUnitOfWork


pytestmark = pytest.mark.asyncio


async def test_sqlite_tenant_uow_commits_and_rolls_back() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    table = sa.Table(
        'uow_rows',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with TenantUnitOfWork(engine, 'workspace-a') as uow:
            await uow.execute(sa.insert(table).values(id=1, workspace_uuid='workspace-a'))

        with pytest.raises(RuntimeError, match='roll back'):
            async with TenantUnitOfWork(engine, 'workspace-a') as uow:
                await uow.execute(sa.insert(table).values(id=2, workspace_uuid='workspace-a'))
                raise RuntimeError('roll back this transaction')

        async with engine.connect() as conn:
            rows = (await conn.execute(sa.select(table.c.id).order_by(table.c.id))).scalars().all()
        assert rows == [1]
    finally:
        await engine.dispose()


async def test_tenant_uow_is_single_use_and_requires_an_active_scope() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    uow = TenantUnitOfWork(engine, 'workspace-a')
    try:
        with pytest.raises(RuntimeError, match='not active'):
            _ = uow.session

        async with uow:
            assert uow.session.in_transaction()

        with pytest.raises(RuntimeError, match='cannot be reused'):
            async with uow:
                pass
    finally:
        await engine.dispose()


def test_persistence_mode_must_be_a_trusted_enum() -> None:
    with pytest.raises(TypeError, match='trusted PersistenceMode'):
        PersistenceManager(object(), mode='cloud_runtime')  # type: ignore[arg-type]

    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    assert manager.mode is PersistenceMode.CLOUD_RUNTIME
