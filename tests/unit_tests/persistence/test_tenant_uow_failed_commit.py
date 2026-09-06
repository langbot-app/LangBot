"""Real rollback-journal contention must not poison the pooled writer."""

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSessionTransaction, create_async_engine

from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import TenantScopedAsyncSession


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_commit', [False, True])
@pytest.mark.parametrize('close_fails', [False, True])
@pytest.mark.parametrize('cancel_cleanup', [False, True])
async def test_failed_commit_releases_sqlite_writer_and_scope(
    tmp_path, monkeypatch, cancel_commit, close_fails, cancel_cleanup
):
    path = tmp_path / 'failed-commit.db'
    engine = create_async_engine(
        f'sqlite+aiosqlite:///{path}', connect_args={'timeout': 0.05}, pool_size=1, max_overflow=0
    )
    table = sa.Table('rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    original_commit = AsyncSessionTransaction.commit
    original_error = None
    invalidation_finished = False
    owner = asyncio.current_task()
    original_invalidate = AsyncConnection.invalidate

    async def delayed_invalidate(connection, exception=None):
        nonlocal invalidation_finished
        if cancel_cleanup:
            owner.cancel()
            await asyncio.sleep(0)
            owner.cancel()
            await asyncio.sleep(0)
        await original_invalidate(connection, exception)
        invalidation_finished = True

    monkeypatch.setattr(AsyncConnection, 'invalidate', delayed_invalidate)

    async def failing_commit(transaction):
        nonlocal original_error
        try:
            await original_commit(transaction)
        except sa.exc.OperationalError as exc:
            original_error = asyncio.CancelledError('commit cancelled') if cancel_commit else exc
            raise original_error

    monkeypatch.setattr(AsyncSessionTransaction, 'commit', failing_commit)
    original_close = TenantScopedAsyncSession._close_owned_session

    async def failing_close(session, capability):
        await original_close(session, capability)
        if original_error is not None:
            raise RuntimeError('secondary close failure')

    if close_fails:
        monkeypatch.setattr(TenantScopedAsyncSession, '_close_owned_session', failing_close)
    blocker = sqlite3.connect(path, timeout=0.05)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(table.metadata.create_all)
            await connection.execute(sa.insert(table).values(id=1))
        blocker.execute('BEGIN')
        blocker.execute('SELECT * FROM rows').fetchall()
        error_type = asyncio.CancelledError if cancel_commit else sa.exc.OperationalError
        with pytest.raises(error_type) as caught:
            async with manager.tenant_uow('workspace-a') as outer:
                gate = manager.create_after_commit_gate()
                state = outer._active_state
                async with manager.tenant_uow('workspace-a') as inner:
                    assert inner.session is outer.session
                    await manager.execute_async(sa.insert(table).values(id=2))
                assert not gate.done()
                assert state.depth == 1
        assert caught.value is original_error
        assert invalidation_finished
        if cancel_cleanup:
            # Do not leak the synthetic cancellation count into pytest.
            owner.uncancel()
            owner.uncancel()
        monkeypatch.setattr(TenantScopedAsyncSession, '_close_owned_session', original_close)
        if close_fails:
            assert any('secondary close failure' in note for note in caught.value.__notes__)
        assert gate.cancelled()
        assert state.depth == 0
        assert manager.current_session() is None
        with pytest.raises(RuntimeError, match='not active'):
            _ = outer.session

        # The original SHARED lock remains. New reads and RESERVED writes
        # must work; COMMIT of another write must wait for its release.
        assert blocker.in_transaction
        with contextlib.closing(sqlite3.connect(path, timeout=0.05)) as probe:
            assert probe.execute('SELECT id FROM rows').fetchall() == [(1,)]
            probe.execute('INSERT INTO rows VALUES (3)')
            probe.rollback()
        async with manager.tenant_uow('workspace-b'):
            assert (await manager.execute_async(sa.select(table.c.id))).scalars().all() == [1]
        blocker.rollback()
        async with manager.tenant_uow('workspace-b'):
            await manager.execute_async(sa.insert(table).values(id=4))
        async with engine.connect() as connection:
            assert (await connection.execute(sa.select(table.c.id).order_by(table.c.id))).scalars().all() == [1, 4]
        assert engine.pool.checkedout() == 0
    finally:
        blocker.close()
        await engine.dispose()
