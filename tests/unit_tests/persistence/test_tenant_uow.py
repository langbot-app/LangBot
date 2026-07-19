from __future__ import annotations

import asyncio
import contextvars
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_object_session
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry, relationship, with_loader_criteria
from sqlalchemy.sql import quoted_name

from langbot.pkg.core.task_boundary import create_detached_task
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import (
    CrossScopeTransactionError,
    PersistenceScopeKind,
    ScopedSessionTransactionError,
    TenantScopedSyncSession,
    TenantScopeRequiredError,
    TenantUnitOfWork,
    TransactionRollbackOnlyError,
    _validate_scoped_statement_call,
)


pytestmark = pytest.mark.asyncio


def _on_conflict_statement(*, update_value, update_key='value', index_element=None):
    table = sa.table('conflict_rows', sa.column('id'), sa.column('value'))
    if index_element is None:
        index_element = table.c.id
    return (
        sqlite_insert(table)
        .values(id=1, value=1)
        .on_conflict_do_update(
            index_elements=[index_element],
            set_={update_key: update_value},
        )
    )


def _on_conflict_constraint_statement(*, constraint):
    table = sa.table('conflict_rows', sa.column('id'), sa.column('value'))
    return (
        postgresql_insert(table)
        .values(id=1, value=1)
        .on_conflict_do_update(
            constraint=constraint,
            set_={'value': 2},
        )
    )


def _multi_value_statement(*, value, value_key='value'):
    table = sa.table('multi_value_rows', sa.column('id'), sa.column('value'))
    return sa.insert(table).values([{'id': 1, value_key: value}])


class _SpoofedCount(sa.sql.functions.FunctionElement):
    name = 'count'
    inherit_cache = True


class _UntrustedCastType(sa.types.UserDefinedType):
    def get_col_spec(self, **kwargs) -> str:
        del kwargs
        return 'INTEGER'


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


async def test_captured_session_rejects_child_task_database_access(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "captured-session-child.db"}')
    table = sa.Table('captured_session_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    mapper_registry = registry()

    class CapturedSessionRow:
        pass

    mapper_registry.map_imperatively(CapturedSessionRow, table)
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_uow('workspace-a') as uow:
            captured_session = uow.session
            captured_execute = captured_session.execute
            captured_add = captured_session.add
            await captured_session.execute(sa.insert(table).values(id=1))

            async def inherited_session_write() -> None:
                await captured_execute(sa.insert(table).values(id=2))

            with pytest.raises(CrossScopeTransactionError, match='cannot be inherited by child tasks'):
                await asyncio.create_task(inherited_session_write())

            async def inherited_session_mutation() -> None:
                captured_add(CapturedSessionRow(id=2))

            with pytest.raises(CrossScopeTransactionError, match='cannot be inherited by child tasks'):
                await asyncio.create_task(inherited_session_mutation())

            # The rejected child never touched the connection and therefore
            # must not poison valid work still owned by the parent task.
            await captured_session.execute(sa.insert(table).values(id=3))

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id).order_by(table.c.id))).scalars().all() == [1, 3]
    finally:
        await engine.dispose()


async def test_captured_session_is_permanently_inactive_after_uow_exit(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "captured-session-exit.db"}')
    table = sa.Table('captured_session_exit_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_uow('workspace-a') as uow:
            captured_session = uow.session
            captured_execute = captured_session.execute
            await captured_execute(sa.insert(table).values(id=1))

        with pytest.raises(ScopedSessionTransactionError, match='no longer active'):
            await captured_session.execute(sa.select(table))
        with pytest.raises(ScopedSessionTransactionError, match='no longer active'):
            await captured_execute(sa.select(table))
        with pytest.raises(ScopedSessionTransactionError, match='no longer active'):
            captured_session.in_transaction()

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id))).scalars().all() == [1]
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    'operation',
    [
        'begin',
        'commit',
        'rollback',
        'close',
        'close_all',
        'connection',
        'get_bind',
        'bind',
        'sync_session',
        'stream',
        'stream_scalars',
    ],
)
async def test_scoped_session_cannot_escape_uow_transaction_lifecycle(tmp_path, operation: str) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / f"session-escape-{operation}.db"}')
    table = sa.Table('session_escape_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with manager.tenant_uow('workspace-a') as uow:
                await uow.execute(sa.insert(table).values(id=1))
                with pytest.raises(ScopedSessionTransactionError, match=f'direct {operation}'):
                    if operation == 'begin':
                        uow.session.begin()
                    elif operation == 'commit':
                        await uow.session.commit()
                    elif operation == 'rollback':
                        await uow.session.rollback()
                    elif operation == 'close':
                        await uow.session.close()
                    elif operation == 'close_all':
                        await uow.session.close_all()
                    elif operation == 'connection':
                        await uow.session.connection()
                    elif operation == 'get_bind':
                        uow.session.get_bind().connect()
                    elif operation == 'bind':
                        _ = uow.session.bind
                    elif operation == 'sync_session':
                        _ = uow.session.sync_session
                    elif operation == 'stream':
                        await uow.session.stream(sa.select(table))
                    else:
                        await uow.session.stream_scalars(sa.select(table.c.id))

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table))).all() == []
    finally:
        await engine.dispose()


async def test_scoped_session_no_autoflush_keeps_the_sync_proxy_private(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "no-autoflush.db"}')
    table = sa.Table('no_autoflush_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    mapper_registry = registry()

    class NoAutoflushRow:
        pass

    mapper_registry.map_imperatively(NoAutoflushRow, table)
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        async with manager.tenant_uow('workspace-a') as uow:
            assert uow.session.autoflush is True
            with uow.session.no_autoflush:
                assert uow.session.autoflush is False
                uow.session.add(NoAutoflushRow(id=1))
            assert uow.session.autoflush is True

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table.c.id))).scalars().all() == [1]
    finally:
        await engine.dispose()


@pytest.mark.parametrize('access_kind', ['async_instance', 'global_sync'])
async def test_orm_object_cannot_expose_the_uow_sync_session(tmp_path, access_kind: str) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / f"object-session-{access_kind}.db"}')
    table = sa.Table('object_session_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    mapper_registry = registry()

    class ObjectSessionRow:
        pass

    mapper_registry.map_imperatively(ObjectSessionRow, table)
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with manager.tenant_uow('workspace-a') as uow:
                row = ObjectSessionRow(id=1)
                uow.session.add(row)
                await uow.session.flush()
                assert async_object_session(row) is uow.session
                gate = manager.create_after_commit_gate()
                assert gate is not None

                if access_kind == 'async_instance':
                    with pytest.raises(ScopedSessionTransactionError, match='object_session access'):
                        uow.session.object_session(row)
                else:
                    sync_session = sa.orm.object_session(row)
                    assert sync_session is not None
                    with pytest.raises(ScopedSessionTransactionError, match='synchronous Session access'):
                        sync_session.rollback()

        assert gate.cancelled()
        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table))).all() == []
    finally:
        await engine.dispose()


@pytest.mark.parametrize('event_name', ['do_orm_execute', 'before_flush'])
async def test_orm_session_events_fail_closed_before_callbacks_run(tmp_path, event_name: str) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / f"orm-event-{event_name}.db"}')
    table = sa.Table('orm_event_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    mapper_registry = registry()

    class EventRow:
        pass

    mapper_registry.map_imperatively(EventRow, table)
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    callback_called = False
    listener_registered = False

    def do_orm_execute_escape(state) -> None:
        nonlocal callback_called
        callback_called = True
        state.session.connection().exec_driver_sql('COMMIT')

    def before_flush_escape(session, flush_context, instances) -> None:
        nonlocal callback_called
        del flush_context, instances
        callback_called = True
        session.bind.connect()

    listener = do_orm_execute_escape if event_name == 'do_orm_execute' else before_flush_escape
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with manager.tenant_uow('workspace-a') as uow:
                await uow.execute(sa.insert(table).values(id=1))
                sa.event.listen(TenantScopedSyncSession, event_name, listener)
                listener_registered = True
                with pytest.raises(ScopedSessionTransactionError, match=f'event listener {event_name}'):
                    if event_name == 'do_orm_execute':
                        await uow.session.execute(sa.select(table))
                    else:
                        uow.session.add(EventRow(id=2))
                        await uow.session.flush()

        assert not callback_called
        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table))).all() == []
    finally:
        if listener_registered:
            sa.event.remove(TenantScopedSyncSession, event_name, listener)
        await engine.dispose()


async def test_pre_registered_orm_session_event_prevents_uow_start() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    callback_called = False

    def after_transaction_create_escape(session, transaction) -> None:
        nonlocal callback_called
        del session, transaction
        callback_called = True

    sa.event.listen(TenantScopedSyncSession, 'after_transaction_create', after_transaction_create_escape)
    try:
        with pytest.raises(ScopedSessionTransactionError, match='event listener after_transaction_create'):
            async with TenantUnitOfWork(engine, 'workspace-a'):
                pass
        assert not callback_called
    finally:
        sa.event.remove(TenantScopedSyncSession, 'after_transaction_create', after_transaction_create_escape)
        await engine.dispose()


async def test_explicit_async_refresh_loads_relationship_without_exposing_sync_session(tmp_path) -> None:
    class Base(DeclarativeBase):
        pass

    class Parent(Base):
        __tablename__ = 'async_attr_parents'

        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates='parent')

    class Child(Base):
        __tablename__ = 'async_attr_children'

        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int] = mapped_column(sa.ForeignKey('async_attr_parents.id'))
        parent: Mapped[Parent] = relationship(back_populates='children')

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "async-attrs.db"}')
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with manager.tenant_uow('workspace-a') as uow:
            uow.session.add(Parent(id=1, children=[Child(id=1)]))

        async with manager.tenant_uow('workspace-a') as uow:
            parent = await uow.session.get(Parent, 1)
            assert parent is not None
            assert 'children' not in parent.__dict__
            await uow.session.refresh(parent, ['children'])
            assert [child.id for child in parent.children] == [1]
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ('statement', 'params', 'keyword_call'),
    [
        (sa.text('ROLLBACK'), None, False),
        (sa.text('/* caller comment */ COMMIT'), None, False),
        (sa.text('SET LOCAL langbot.workspace_uuid = :value'), {'value': 'workspace-b'}, False),
        (sa.text("SET LOCAL langbot . workspace_uuid = 'workspace-b'"), None, False),
        (sa.text("SET/**/ LOCAL /**/ langbot . workspace_uuid = 'workspace-b'"), None, False),
        (
            sa.text('SELECT set_config(:setting_name, :setting_value, true)'),
            {'setting_name': 'langbot.workspace_uuid', 'setting_value': 'workspace-b'},
            False,
        ),
        (
            sa.text('SELECT set_config/**/(:setting_name, :setting_value, true)'),
            {'setting_name': 'langbot.workspace_uuid', 'setting_value': 'workspace-b'},
            False,
        ),
        (
            sa.text('SELECT "set_config"(:setting_name, :setting_value, true)'),
            {'setting_name': 'langbot.workspace_uuid', 'setting_value': 'workspace-b'},
            False,
        ),
        (sa.text("DO $$ BEGIN PERFORM set_config('langbot.workspace_uuid', 'workspace-b', true); END $$"), None, False),
        (sa.text('CALL tenant_scope_escape()'), None, False),
        (sa.text('CREATE FUNCTION tenant_scope_escape() RETURNS void LANGUAGE SQL AS $$ SELECT 1 $$'), None, False),
        (sa.text('SELECT * INTO TEMP leaked_rows FROM sql_escape_rows'), None, False),
        (sa.text('SELECT * INTO pg_temp.leaked_rows FROM sql_escape_rows'), None, False),
        (sa.text('DECLARE leaked_rows CURSOR WITH HOLD FOR SELECT * FROM sql_escape_rows'), None, False),
        (sa.text('FETCH ALL FROM leaked_rows'), None, False),
        (sa.text('PREPARE scope_escape AS SELECT 1'), None, False),
        (sa.text('EXECUTE scope_escape'), None, False),
        (sa.text('EXPLAIN (ANALYZE true) EXECUTE scope_escape'), None, False),
        (sa.text('LISTEN tenant_scope_escape'), None, False),
        (sa.text("NOTIFY tenant_scope_escape, 'payload'"), None, False),
        (sa.text('LOCK TABLE sql_escape_rows'), None, False),
        (sa.text('SELECT pg_advisory_lock(123)'), None, False),
        (sa.text('VALUES (pg_try_advisory_lock(123))'), None, False),
        (sa.text('EXPLAIN (ANALYZE TRUE) SELECT pg_advisory_lock(123)'), None, False),
        (sa.text("SELECT pg_notify('tenant_scope_escape', 'payload')"), None, False),
        (sa.text("SELECT lo_from_bytea(0, decode('AA==', 'base64'))"), None, False),
        (sa.text('SELECT lo_get(123)'), None, False),
        (sa.text("SELECT currval('shared_sequence')"), None, False),
        (sa.text('SELECT lastval()'), None, False),
        (
            sa.select(
                sa.func.query_to_xml(
                    sa.literal('SELECT 1'),
                    sa.literal(True),
                    sa.literal(False),
                    sa.literal(''),
                )
            ),
            None,
            False,
        ),
        (sa.select(sa.func.ts_stat(sa.literal('SELECT 1'))), None, False),
        (sa.select(sa.func.pg_catalog.count()), None, False),
        (sa.select(_SpoofedCount()), None, False),
        (sa.select(sa.literal_column('1')), None, False),
        (sa.select(sa.text('1')), None, False),
        (sa.select(sa.bindparam('value', 1, literal_execute=True)), None, False),
        (sa.select(sa.bindparam('value', 1, type_=_UntrustedCastType())), None, False),
        (sa.select(sa.column('value').op('@@')(sa.literal('query'))), None, False),
        (
            sa.select(
                sa.sql.expression.UnaryExpression(
                    sa.literal(True),
                    operator=sa.sql.operators.custom_op('unsafe_prefix'),
                )
            ),
            None,
            False,
        ),
        (
            sa.select(
                sa.sql.expression.UnaryExpression(
                    sa.literal(True),
                    modifier=sa.sql.operators.custom_op('unsafe_suffix'),
                )
            ),
            None,
            False,
        ),
        (sa.select(sa.extract('year', sa.literal('2026-01-01'))), None, False),
        (sa.select(sa.cast(sa.literal(1), _UntrustedCastType())), None, False),
        (
            sa.select(User).options(with_loader_criteria(User, sa.literal_column('1 = 1'))),
            None,
            False,
        ),
        (sa.select(sa.table(quoted_name('forced unquoted table', quote=False))), None, False),
        (sa.select(sa.literal(1).label(quoted_name('forced unquoted label', quote=False))), None, False),
        (
            sa.select(sa.collate(sa.column('value'), quoted_name('forced unquoted collation', quote=False))),
            None,
            False,
        ),
        (sa.select(sa.literal(1)).prefix_with('/* caller prefix */'), None, False),
        (sa.select(sa.literal(1)).suffix_with('FOR UPDATE'), None, False),
        (sa.select(sa.literal(1)).with_statement_hint('caller hint'), None, False),
        (
            _on_conflict_statement(
                update_value=sa.func.query_to_xml(
                    sa.literal('SELECT 1'),
                    sa.literal(True),
                    sa.literal(False),
                    sa.literal(''),
                )
            ),
            None,
            False,
        ),
        (_on_conflict_statement(update_value=sa.text('set_config(:name, :value, true)')), None, False),
        (
            _on_conflict_statement(
                update_value=1,
                update_key=quoted_name('forced unquoted update', quote=False),
            ),
            None,
            False,
        ),
        (
            _on_conflict_statement(
                update_value=1,
                index_element=quoted_name('forced unquoted target', quote=False),
            ),
            None,
            False,
        ),
        (
            _on_conflict_constraint_statement(constraint=quoted_name('forced unquoted constraint', quote=False)),
            None,
            False,
        ),
        (_multi_value_statement(value=sa.func.ts_stat(sa.literal('SELECT 1'))), None, False),
        (_multi_value_statement(value=sa.text('set_config(:name, :value, true)')), None, False),
        (
            _multi_value_statement(
                value=1,
                value_key=quoted_name('forced unquoted batch key', quote=False),
            ),
            None,
            False,
        ),
        (sa.values(sa.column('value')).data([(sa.func.ts_stat(sa.literal('SELECT 1')),)]), None, False),
        (
            sa.insert(sa.table('rows', sa.column('value'))).from_select(
                ['value'],
                sa.select(sa.literal(1)),
            ),
            None,
            False,
        ),
        (sa.text('ROLLBACK'), None, True),
        (
            sa.text('SELECT set_config(:setting_name, :setting_value, true)'),
            {'setting_name': 'langbot.workspace_uuid', 'setting_value': 'workspace-b'},
            True,
        ),
    ],
)
async def test_scoped_session_rejects_raw_or_unapproved_sql(
    tmp_path,
    statement,
    params,
    keyword_call: bool,
) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "sql-transaction-escape.db"}')
    table = sa.Table('sql_escape_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='after-commit work was cancelled'):
            async with manager.tenant_uow('workspace-a') as uow:
                await uow.execute(sa.insert(table).values(id=1))
                gate = manager.create_after_commit_gate()
                assert gate is not None
                with pytest.raises(ScopedSessionTransactionError):
                    if keyword_call:
                        await uow.session.execute(statement=statement, params=params)
                    elif params is None:
                        await uow.session.execute(statement)
                    else:
                        await uow.session.execute(statement, params)

        assert gate.cancelled()
        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(table))).all() == []
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    'statement',
    [
        sa.select(sa.literal('set_config(')),
        sa.select(sa.func.count()),
        sa.select(sa.func.coalesce(sa.func.sum(sa.literal(1)), sa.literal(0))),
        sa.select(
            sa.func.now(),
            sa.func.length(sa.literal('value')),
            sa.func.nullif(sa.literal('value'), sa.literal('')),
        ),
        sa.select(sa.column('embedding').op('<=>')(sa.literal([0.1]))),
        sa.select(sa.cast(sa.column('embedding'), Vector(384))),
        sa.insert(sa.table('rows', sa.column('id'))).values(id=1),
        _multi_value_statement(value=1),
        _on_conflict_statement(update_value=sa.func.coalesce(sa.literal(1), sa.literal(0))),
    ],
)
async def test_scoped_sql_structure_allows_only_the_production_vocabulary(statement) -> None:
    _validate_scoped_statement_call((statement,), {})


async def test_scoped_sql_rejects_public_execution_options() -> None:
    statement = sa.select(sa.literal(1))
    with pytest.raises(ScopedSessionTransactionError, match='execution options'):
        _validate_scoped_statement_call(
            (statement,),
            {'execution_options': {'schema_translate_map': {None: 'other_schema'}}},
        )


@pytest.mark.parametrize('operation', ['get', 'get_one', 'refresh', 'merge'])
async def test_scoped_orm_loaders_reject_public_query_options(operation: str) -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with TenantUnitOfWork(engine, 'workspace-a') as uow:
                with pytest.raises(ScopedSessionTransactionError, match=operation):
                    if operation == 'get':
                        await uow.session.get(
                            User,
                            1,
                            execution_options={'schema_translate_map': {None: 'other_schema'}},
                        )
                    elif operation == 'get_one':
                        await uow.session.get_one(User, 1, options=[object()])
                    elif operation == 'refresh':
                        await uow.session.refresh(object(), with_for_update=True)
                    else:
                        await uow.session.merge(User(), options=[object()])
    finally:
        await engine.dispose()


async def test_scoped_get_rejects_empty_for_update_mapping() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with TenantUnitOfWork(engine, 'workspace-a') as uow:
                with pytest.raises(ScopedSessionTransactionError, match='get option with_for_update'):
                    await uow.session.get(User, 1, with_for_update={})
    finally:
        await engine.dispose()


@pytest.mark.parametrize('flush_kind', ['explicit', 'autoflush'])
async def test_scoped_orm_writes_reject_attribute_sql_expressions(tmp_path, flush_kind: str) -> None:
    class Base(DeclarativeBase):
        pass

    class Row(Base):
        __tablename__ = f'orm_expression_{flush_kind}'

        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int] = mapped_column()

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / f"orm-expression-{flush_kind}.db"}')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with TenantUnitOfWork(engine, 'workspace-a') as uow:
                uow.session.add(Row(id=1, value=sa.literal_column('40 + 2')))
                with pytest.raises(ScopedSessionTransactionError, match='ORM SQL expression'):
                    if flush_kind == 'explicit':
                        await uow.session.flush()
                    else:
                        await uow.session.execute(sa.select(Row.id))

        async with engine.connect() as conn:
            assert (await conn.execute(sa.select(Row))).all() == []
    finally:
        await engine.dispose()


async def test_scoped_session_rejects_an_explicit_foreign_bind(tmp_path) -> None:
    primary = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "primary-bind.db"}')
    foreign = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "foreign-bind.db"}')
    table = sa.Table('bind_escape_rows', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: primary)
    try:
        for engine in (primary, foreign):
            async with engine.begin() as conn:
                await conn.run_sync(table.metadata.create_all)

        with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
            async with manager.tenant_uow('workspace-a') as uow:
                await uow.execute(sa.insert(table).values(id=1))
                with pytest.raises(ScopedSessionTransactionError, match='foreign database bind'):
                    await uow.session.execute(
                        sa.insert(table).values(id=2),
                        bind_arguments={'bind': foreign.sync_engine},
                    )

        for engine in (primary, foreign):
            async with engine.connect() as conn:
                assert (await conn.execute(sa.select(table))).all() == []
    finally:
        await primary.dispose()
        await foreign.dispose()


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
