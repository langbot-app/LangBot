from __future__ import annotations

import asyncio
import contextvars
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.core.task_boundary import create_detached_task
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import (
    CrossScopeTransactionError,
    PersistenceScopeKind,
    TenantScopeRequiredError,
    TenantUnitOfWork,
    TransactionRollbackOnlyError,
)


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


async def test_manager_reuses_one_session_and_rejects_cross_workspace(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "manager-uow.db"}')
    table = sa.Table(
        'manager_rows',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
    )
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TenantScopeRequiredError, match='explicit Workspace or discovery'):
            await manager.execute_async(sa.select(table))

        async with manager.tenant_uow('workspace-a') as outer:
            await manager.execute_async(sa.insert(table).values(id=1, workspace_uuid='workspace-a'))
            async with manager.tenant_uow('workspace-a') as inner:
                assert inner.session is outer.session
                assert manager.current_session() is outer.session
                assert (await manager.execute_async(sa.select(table.c.id))).scalar_one() == 1
            with pytest.raises(CrossScopeTransactionError, match='while workspace scope is active'):
                async with manager.tenant_uow('workspace-b'):
                    pass

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id))).scalars().all() == [1]
    finally:
        await engine.dispose()


async def test_manager_scoped_execute_preserves_core_row_and_scalar_contract(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "manager-result-contract.db"}')
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(User.__table__.create)
            await conn.execute(
                sa.insert(User).values(
                    uuid='account-a',
                    user='owner@example.com',
                    normalized_email='owner@example.com',
                    password='hashed-password',
                )
            )

        async with manager.tenant_uow('workspace-a') as uow:
            result = await manager.execute_async(sa.select(User))
            row = result.first()
            assert row is not None
            assert row.uuid == 'account-a'
            assert row.user == 'owner@example.com'

            scalar_result = await manager.execute_async(sa.select(User.uuid))
            assert scalar_result.scalar_one() == 'account-a'

            list_result = await manager.execute_async(sa.select(User.user))
            assert list_result.scalars().all() == ['owner@example.com']

            # Direct UoW execution remains an ORM API for code that opts into it.
            orm_result = await uow.execute(sa.select(User))
            assert orm_result.scalars().one().uuid == 'account-a'
    finally:
        await engine.dispose()


async def test_transaction_free_tenant_scope_opens_one_short_uow_per_database_call(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "short-scope.db"}')
    table = sa.Table(
        'short_scope_rows',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
    )
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_scope('workspace-a'):
            assert manager.current_scope() is not None
            assert manager.current_scope().kind is PersistenceScopeKind.WORKSPACE
            assert manager.current_scope().settings == (('langbot.workspace_uuid', 'workspace-a'),)
            assert manager.current_session() is None

            await manager.execute_async(sa.insert(table).values(id=1, workspace_uuid='workspace-a'))
            assert manager.current_session() is None

            # The first statement has already committed. Long external waits
            # inside this boundary retain only identity, never a DB session.
            await asyncio.sleep(0)
            assert manager.current_session() is None

            assert (await manager.execute_async(sa.select(table.c.id))).scalar_one() == 1
            assert manager.current_session() is None

            async with manager.tenant_scope('workspace-a'):
                assert manager.current_session() is None
            with pytest.raises(CrossScopeTransactionError, match='while workspace scope is active'):
                async with manager.tenant_scope('workspace-b'):
                    pass
            with pytest.raises(CrossScopeTransactionError, match='while workspace scope is active'):
                async with manager.tenant_uow('workspace-b'):
                    pass

        assert manager.current_scope() is None
        with pytest.raises(TenantScopeRequiredError, match='explicit Workspace'):
            await manager.execute_async(sa.select(table))
    finally:
        await engine.dispose()


async def test_transaction_free_scope_requires_explicit_child_task_scope(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "short-scope-child.db"}')
    table = sa.Table('child_scope_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_scope('workspace-a'):

            async def inherited_access() -> None:
                await manager.execute_async(sa.select(table))

            with pytest.raises(CrossScopeTransactionError, match='cannot be inherited by child tasks'):
                await asyncio.create_task(inherited_access())

            async def explicitly_scoped_access() -> None:
                async with manager.tenant_scope('workspace-a'):
                    await manager.execute_async(sa.insert(table).values(id=1))
                    assert manager.current_session() is None

            await asyncio.create_task(explicitly_scoped_access())
            assert manager.current_session() is None

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id))).scalars().all() == [1]
    finally:
        await engine.dispose()


async def test_caught_nested_failure_marks_outer_transaction_rollback_only(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "rollback-only.db"}')
    table = sa.Table('rollback_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with manager.tenant_uow('workspace-a'):
                await manager.execute_async(sa.insert(table).values(id=1))
                try:
                    async with manager.tenant_uow('workspace-a'):
                        raise ValueError('caught nested failure')
                except ValueError:
                    pass

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table))).all() == []
    finally:
        await engine.dispose()


@pytest.mark.parametrize('executor_kind', ['manager', 'uow', 'session'])
async def test_caught_database_error_rolls_back_and_cancels_after_commit_gate(tmp_path, executor_kind: str) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / f"db-error-{executor_kind}.db"}')
    table = sa.Table('unique_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='after-commit work was cancelled'):
            async with manager.tenant_uow('workspace-a') as uow:
                statement = sa.insert(table).values(id=1)
                if executor_kind == 'manager':
                    await manager.execute_async(statement)
                elif executor_kind == 'uow':
                    await uow.execute(statement)
                else:
                    await uow.session.execute(statement)

                gate = manager.create_after_commit_gate()
                assert gate is not None
                try:
                    if executor_kind == 'manager':
                        await manager.execute_async(statement)
                    elif executor_kind == 'uow':
                        await uow.execute(statement)
                    else:
                        await uow.session.execute(statement)
                except sa.exc.IntegrityError:
                    pass

        assert gate.cancelled()
        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table))).all() == []
    finally:
        await engine.dispose()


async def test_child_task_must_open_its_own_explicit_uow(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "child-task.db"}')
    table = sa.Table(
        'child_rows',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
    )
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_uow('workspace-a'):

            async def inherited_access() -> None:
                await manager.execute_async(sa.select(table))

            with pytest.raises(CrossScopeTransactionError, match='cannot be inherited by child tasks'):
                await asyncio.create_task(inherited_access())

            async def explicitly_scoped_access() -> None:
                async with manager.tenant_uow('workspace-a'):
                    await manager.execute_async(sa.insert(table).values(id=2, workspace_uuid='workspace-a'))

            await asyncio.create_task(explicitly_scoped_access())

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id))).scalars().all() == [2]
    finally:
        await engine.dispose()


async def test_detached_task_starts_without_parent_scope_and_rolls_back_its_uow(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "detached-task.db"}')
    table = sa.Table(
        'detached_rows',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('workspace_uuid', sa.String(36), nullable=False),
    )
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_uow('workspace-a'):

            async def detached_write() -> None:
                # Before the detached boundary this access raises
                # CrossScopeTransactionError because asyncio copies the
                # parent's ActiveScopedTransaction into this child task.
                assert manager.current_scope() is None
                async with manager.tenant_uow('workspace-a'):
                    await manager.execute_async(sa.insert(table).values(id=2, workspace_uuid='workspace-a'))
                    raise RuntimeError('roll back detached write')

            task = create_detached_task(detached_write())
            with pytest.raises(RuntimeError, match='roll back detached write'):
                await task

            await manager.execute_async(sa.insert(table).values(id=1, workspace_uuid='workspace-a'))

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id))).scalars().all() == [1]
    finally:
        await engine.dispose()


async def test_after_commit_task_waits_for_commit_and_starts_with_empty_context(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "after-commit.db"}')
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    request_value = contextvars.ContextVar('after_commit_request_value', default=None)
    observed = []
    try:
        async with manager.tenant_uow('workspace-a'):
            token = request_value.set('request-scope')

            async def after_commit_work() -> None:
                observed.append((request_value.get(), manager.current_scope()))

            try:
                task = create_detached_task(
                    after_commit_work(),
                    after_commit_manager=manager,
                )
                await asyncio.sleep(0)
                assert observed == []
            finally:
                request_value.reset(token)

        await task
        assert observed == [(None, None)]
    finally:
        await engine.dispose()


async def test_after_commit_task_is_cancelled_and_coroutine_closed_on_rollback(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "after-rollback.db"}')
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    started = False

    async def should_not_start() -> None:
        nonlocal started
        started = True

    coro = should_not_start()
    try:
        with pytest.raises(RuntimeError, match='rollback request'):
            async with manager.tenant_uow('workspace-a'):
                task = create_detached_task(coro, after_commit_manager=manager)
                await asyncio.sleep(0)
                assert not task.done()
                raise RuntimeError('rollback request')

        await asyncio.sleep(0)
        assert task.cancelled()
        assert not started
        assert coro.cr_frame is None
    finally:
        await engine.dispose()
