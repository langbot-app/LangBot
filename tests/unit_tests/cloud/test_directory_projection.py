from __future__ import annotations

import datetime
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.cloud.directory import (
    DirectoryDelta,
    DirectoryEvent,
    DirectoryEventBatch,
    DirectoryMember,
    DirectoryProjectionLimits,
    DirectoryProjectionUnavailableError,
    DirectorySnapshot,
    DirectoryWorkspace,
)
from langbot.pkg.cloud.directory_projection import DirectoryProjectionService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.cloud_directory import DirectoryProjectionInbox, DirectoryProjectionState
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionState,
    WorkspaceMembership,
)
from langbot.pkg.persistence.tenant_uow import PersistenceScope, TenantUnitOfWork


pytestmark = pytest.mark.asyncio

INSTANCE_UUID = 'instance-directory-test'
WORKSPACE_UUID = '10000000-0000-0000-0000-000000000001'
SECOND_WORKSPACE_UUID = '10000000-0000-0000-0000-000000000002'
ACCOUNT_UUID = '20000000-0000-0000-0000-000000000001'
MEMBERSHIP_UUID = '30000000-0000-0000-0000-000000000001'
SECOND_MEMBERSHIP_UUID = '30000000-0000-0000-0000-000000000002'


class _Persistence:
    def __init__(self, engine):
        self.engine = engine

    def directory_projection_uow(self, instance_uuid: str) -> TenantUnitOfWork:
        return TenantUnitOfWork(
            self.engine,
            scope=PersistenceScope.directory(instance_uuid),
        )

    def get_db_engine(self):
        return self.engine


class _Provider:
    def __init__(
        self,
        snapshots: list[DirectorySnapshot],
        batches: list[DirectoryEventBatch] | None = None,
        deltas: list[DirectoryDelta] | None = None,
    ) -> None:
        self.snapshots = snapshots
        self.batches = list(batches or [])
        self.deltas = list(deltas or [])
        self.snapshot_calls = 0
        self.delta_calls = 0
        self.after_cursors: list[int] = []

    async def fetch_snapshot(self, instance_uuid: str) -> DirectorySnapshot:
        assert instance_uuid == INSTANCE_UUID
        snapshot = self.snapshots[min(self.snapshot_calls, len(self.snapshots) - 1)]
        self.snapshot_calls += 1
        return snapshot

    async def fetch_events(
        self,
        instance_uuid: str,
        after_cursor: int,
        limit: int,
    ) -> DirectoryEventBatch:
        assert instance_uuid == INSTANCE_UUID
        assert limit == 100
        self.after_cursors.append(after_cursor)
        if self.batches:
            return self.batches.pop(0)
        return DirectoryEventBatch(
            instance_uuid=instance_uuid,
            after_cursor=after_cursor,
            cursor=after_cursor,
            high_water_cursor=after_cursor,
            events=[],
        )

    async def fetch_workspaces(
        self,
        instance_uuid: str,
        workspace_uuids: tuple[str, ...],
    ) -> DirectoryDelta:
        assert instance_uuid == INSTANCE_UUID
        assert workspace_uuids == (WORKSPACE_UUID,)
        delta = self.deltas[min(self.delta_calls, len(self.deltas) - 1)]
        self.delta_calls += 1
        return delta


@pytest.fixture
async def projection_context(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "directory-projection.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    application = SimpleNamespace(
        persistence_mgr=_Persistence(engine),
        logger=logging.getLogger('test-directory-projection'),
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield application, session_factory
    await engine.dispose()


def _member(*, revision: int = 1, role: str = 'member') -> DirectoryMember:
    return DirectoryMember(
        membership_uuid=MEMBERSHIP_UUID,
        account_uuid=ACCOUNT_UUID,
        normalized_email='owner@example.com',
        display_name='Workspace Owner',
        account_status='active',
        role=role,
        membership_status='active',
        projection_revision=revision,
        joined_at=datetime.datetime(2026, 7, 24, tzinfo=datetime.UTC),
    )


def _workspace(
    *,
    revision: int = 1,
    status: str = 'active',
    name: str = 'Personal Workspace',
    role: str = 'member',
    execution_generation: int = 1,
) -> DirectoryWorkspace:
    return DirectoryWorkspace(
        uuid=WORKSPACE_UUID,
        name=name,
        slug='personal-workspace',
        type='personal',
        status=status,
        created_by_account_uuid=ACCOUNT_UUID,
        projection_revision=revision,
        execution_generation=execution_generation,
        members=[_member(revision=revision, role=role)],
    )


def _snapshot(
    cursor: int,
    *,
    workspaces: list[DirectoryWorkspace] | None = None,
) -> DirectorySnapshot:
    return DirectorySnapshot(
        instance_uuid=INSTANCE_UUID,
        cursor=cursor,
        generated_at=datetime.datetime(2026, 7, 24, 12, cursor % 60, tzinfo=datetime.UTC),
        workspaces=[_workspace(revision=max(cursor, 1))] if workspaces is None else workspaces,
    )


def _delta(
    *,
    workspaces: list[DirectoryWorkspace] | None = None,
    requested_workspace_uuids: tuple[str, ...] = (WORKSPACE_UUID,),
) -> DirectoryDelta:
    return DirectoryDelta(
        instance_uuid=INSTANCE_UUID,
        requested_workspace_uuids=requested_workspace_uuids,
        generated_at=datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC),
        workspaces=[_workspace(revision=2)] if workspaces is None else workspaces,
    )


async def test_directory_delta_requests_model_catalog_sync_after_commit(projection_context):
    application, _session_factory = projection_context
    request_sync = Mock()
    application.cloud_model_catalog_service = SimpleNamespace(request_sync=request_sync)
    event = DirectoryEvent(
        cursor=2,
        uuid='20000000-0000-4000-8000-000000000002',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 30, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)], [batch], [_delta(workspaces=[_workspace(revision=2)])]),
        INSTANCE_UUID,
    )
    await service.initialize()
    request_sync.reset_mock()

    await service.sync_once()

    request_sync.assert_called_once_with()


async def test_initial_snapshot_projects_core_owned_rows(projection_context):
    application, session_factory = projection_context
    reconcile_execution_projection = Mock()
    application.tool_mgr = SimpleNamespace(
        mcp_tool_loader=SimpleNamespace(
            reconcile_execution_projection=reconcile_execution_projection,
        )
    )
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
    )

    await service.initialize()
    service.require_ready()

    async with session_factory() as session:
        account = await session.scalar(sqlalchemy.select(User))
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
        execution = await session.get(WorkspaceExecutionState, WORKSPACE_UUID)
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)

    assert account is not None
    assert account.uuid == ACCOUNT_UUID
    assert account.source == 'cloud_projection'
    assert account.account_type == 'space'
    assert account.password == ''
    assert workspace is not None
    assert workspace.source == 'cloud_projection'
    assert membership is not None
    assert membership.role == 'developer'
    assert execution is not None
    assert execution.source == 'cloud'
    assert execution.write_fenced is False
    assert state is not None
    assert state.cursor == 1
    assert state.snapshot_coverage_cursor == 1
    reconcile_execution_projection.assert_called_once_with(
        INSTANCE_UUID,
        {WORKSPACE_UUID: 1},
        affected_workspace_uuids=None,
    )


async def test_same_cursor_equivocation_and_rollback_fail_closed(projection_context):
    application, _session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(2)]),
        INSTANCE_UUID,
    )
    await service.initialize()

    conflicting = _snapshot(
        2,
        workspaces=[_workspace(revision=2, name='Conflicting Name')],
    )
    with pytest.raises(DirectoryProjectionUnavailableError, match='conflicting contents'):
        await service.apply_snapshot(conflicting)

    with pytest.raises(DirectoryProjectionUnavailableError, match='rolled back'):
        await service.apply_snapshot(_snapshot(1))


async def test_execution_generation_cannot_change_without_directory_revision(projection_context):
    application, _session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
    )
    await service.initialize()

    conflicting = _snapshot(
        2,
        workspaces=[_workspace(revision=1, execution_generation=2)],
    )
    with pytest.raises(DirectoryProjectionUnavailableError, match='execution state has conflicting contents'):
        await service.apply_snapshot(conflicting)


async def test_event_limit_matches_single_delta_request_limit(projection_context):
    application, _session_factory = projection_context
    with pytest.raises(ValueError, match='between 1 and 100'):
        DirectoryProjectionService(
            application,
            _Provider([_snapshot(1)]),
            INSTANCE_UUID,
            event_limit=101,
        )


async def test_snapshot_capacity_rejects_atomically_before_projection(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
        limits=DirectoryProjectionLimits(
            max_active_workspaces=1,
            max_snapshot_workspaces=1,
            max_snapshot_memberships=1,
        ),
    )
    second_workspace = DirectoryWorkspace(
        uuid=SECOND_WORKSPACE_UUID,
        name='Second Workspace',
        slug='second-workspace',
        type='personal',
        status='active',
        created_by_account_uuid='20000000-0000-0000-0000-000000000002',
        projection_revision=1,
        execution_generation=1,
        members=[
            DirectoryMember(
                membership_uuid=SECOND_MEMBERSHIP_UUID,
                account_uuid='20000000-0000-0000-0000-000000000002',
                normalized_email='second@example.com',
                display_name='Second Owner',
                account_status='active',
                role='owner',
                membership_status='active',
                projection_revision=1,
            )
        ],
    )

    with pytest.raises(DirectoryProjectionUnavailableError, match='Workspace capacity exceeded'):
        await service.apply_snapshot(
            _snapshot(
                1,
                workspaces=[
                    _workspace(),
                    second_workspace,
                ],
            )
        )

    async with session_factory() as session:
        assert await session.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(Workspace)) == 0
        assert await session.get(DirectoryProjectionState, INSTANCE_UUID) is None


async def test_incremental_capacity_rolls_back_without_advancing_cursor(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
        limits=DirectoryProjectionLimits(
            max_active_workspaces=1,
            max_snapshot_workspaces=1,
            max_snapshot_memberships=2,
        ),
    )
    await service.initialize()

    second_account_uuid = '20000000-0000-0000-0000-000000000002'
    second_workspace = DirectoryWorkspace(
        uuid=SECOND_WORKSPACE_UUID,
        name='Second Workspace',
        slug='second-workspace',
        type='personal',
        status='active',
        created_by_account_uuid=second_account_uuid,
        projection_revision=2,
        execution_generation=1,
        members=[
            DirectoryMember(
                membership_uuid=SECOND_MEMBERSHIP_UUID,
                account_uuid=second_account_uuid,
                normalized_email='second@example.com',
                display_name='Second Owner',
                account_status='active',
                role='owner',
                membership_status='active',
                projection_revision=2,
            )
        ],
    )
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000002',
        aggregate_uuid=SECOND_WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={
            'workspace_uuid': SECOND_WORKSPACE_UUID,
            'directory_revision': 2,
        },
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    delta = DirectoryDelta(
        instance_uuid=INSTANCE_UUID,
        requested_workspace_uuids=[SECOND_WORKSPACE_UUID],
        generated_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
        workspaces=[second_workspace],
    )

    with pytest.raises(DirectoryProjectionUnavailableError, match='Projected active Workspace capacity exceeded'):
        await service.apply_delta(delta, batch)

    async with session_factory() as session:
        assert await session.get(Workspace, SECOND_WORKSPACE_UUID) is None
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)
        assert state is not None
        assert state.cursor == 1
    assert service.resource_snapshot()['active_workspaces'] == 1


async def test_account_projection_reads_large_directory_in_bounded_batches(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
    )
    workspaces = []
    for number in range(501):
        account_uuid = f'20000000-0000-0000-0000-{number:012d}'
        workspaces.append(
            DirectoryWorkspace(
                uuid=f'10000000-0000-0000-0000-{number:012d}',
                name=f'Workspace {number}',
                slug=f'workspace-{number}',
                type='personal',
                status='active',
                created_by_account_uuid=account_uuid,
                projection_revision=1,
                execution_generation=1,
                members=[
                    DirectoryMember(
                        membership_uuid=f'30000000-0000-0000-0000-{number:012d}',
                        account_uuid=account_uuid,
                        normalized_email=f'owner-{number}@example.com',
                        display_name=f'Owner {number}',
                        account_status='active',
                        role='owner',
                        membership_status='active',
                        projection_revision=1,
                    )
                ],
            )
        )
    snapshot = _snapshot(1, workspaces=workspaces)
    user_selects = 0

    def count_user_selects(_connection, _cursor, statement, _parameters, _context, _executemany):
        nonlocal user_selects
        if statement.lstrip().upper().startswith('SELECT') and 'users' in statement:
            user_selects += 1

    engine = application.persistence_mgr.engine
    sqlalchemy.event.listen(engine.sync_engine, 'before_cursor_execute', count_user_selects)
    try:
        async with application.persistence_mgr.directory_projection_uow(INSTANCE_UUID) as uow:
            projected = await service._apply_accounts(uow.session, snapshot)
    finally:
        sqlalchemy.event.remove(engine.sync_engine, 'before_cursor_execute', count_user_selects)

    assert len(projected) == 501
    assert user_selects == 2
    async with session_factory() as session:
        assert await session.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(User)) == 501


async def test_archived_and_absent_workspaces_are_execution_fenced(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
    )
    await service.initialize()

    await service.apply_snapshot(
        _snapshot(
            2,
            workspaces=[_workspace(revision=2, status='archived')],
        )
    )
    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        execution = await session.get(WorkspaceExecutionState, WORKSPACE_UUID)
        membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
        assert workspace.status == 'archived'
        assert execution.state == 'inactive'
        assert execution.write_fenced is True
        assert membership.status == 'removed'

    await service.apply_snapshot(_snapshot(3, workspaces=[]))
    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        execution = await session.get(WorkspaceExecutionState, WORKSPACE_UUID)
        assert workspace.status == 'archived'
        assert execution.state == 'inactive'
        assert execution.write_fenced is True


async def test_event_poll_fetches_workspace_delta_and_records_receipt(projection_context):
    application, session_factory = projection_context
    reconcile_execution_projection = Mock()
    application.tool_mgr = SimpleNamespace(
        mcp_tool_loader=SimpleNamespace(
            reconcile_execution_projection=reconcile_execution_projection,
        )
    )
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000001',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    provider = _Provider(
        [_snapshot(1)],
        [batch],
        [_delta(workspaces=[_workspace(revision=2, name='Updated Workspace')])],
    )
    service = DirectoryProjectionService(application, provider, INSTANCE_UUID)
    await service.initialize()
    reconcile_execution_projection.reset_mock()

    await service.sync_once()

    async with session_factory() as session:
        account = await session.scalar(sqlalchemy.select(User).where(User.uuid == ACCOUNT_UUID))
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)
        inbox = await session.scalar(sqlalchemy.select(DirectoryProjectionInbox))
    assert account.projection_revision == 1
    assert workspace.name == 'Updated Workspace'
    assert state.cursor == 2
    assert inbox.event_uuid == event.uuid
    assert inbox.applied_at is not None
    assert provider.snapshot_calls == 1
    assert provider.delta_calls == 1
    reconcile_execution_projection.assert_called_once_with(
        INSTANCE_UUID,
        {WORKSPACE_UUID: 1},
        affected_workspace_uuids={WORKSPACE_UUID},
    )


async def test_directory_delta_does_not_skip_unfetched_event_cursors(projection_context):
    application, session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000003',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=3,
        events=[event],
    )
    provider = _Provider(
        [_snapshot(1)],
        [batch],
        [_delta(workspaces=[_workspace(revision=3, name='Latest Workspace')])],
    )
    service = DirectoryProjectionService(application, provider, INSTANCE_UUID)
    await service.initialize()

    await service.sync_once()

    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)
    assert workspace.name == 'Latest Workspace'
    assert state.cursor == 2


async def test_entitlement_event_advances_cursor_without_refetching_directory(projection_context):
    application, session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000002',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='entitlement.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'entitlement_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    provider = _Provider([_snapshot(1)], [batch])
    service = DirectoryProjectionService(application, provider, INSTANCE_UUID)
    await service.initialize()

    await service.sync_once()
    await service.apply_snapshot(_snapshot(2, workspaces=[_workspace(revision=1)]))

    async with session_factory() as session:
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)
        inbox = await session.scalar(sqlalchemy.select(DirectoryProjectionInbox))
    assert provider.snapshot_calls == 1
    assert state.cursor == 2
    assert inbox.event_uuid == event.uuid
    assert inbox.applied_at is not None


async def test_missing_workspace_in_delta_fences_only_requested_workspace(projection_context):
    application, session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000004',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    provider = _Provider([_snapshot(1)], [batch], [_delta(workspaces=[])])
    service = DirectoryProjectionService(application, provider, INSTANCE_UUID)
    await service.initialize()

    await service.sync_once()

    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        execution = await session.get(WorkspaceExecutionState, WORKSPACE_UUID)
        membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
    assert workspace.status == 'archived'
    assert workspace.projection_revision == 2
    assert execution.state == 'inactive'
    assert execution.write_fenced is True
    assert execution.desired_state_revision == 2
    assert membership.status == 'removed'
    assert membership.projection_revision == 2

    stale_same_cursor_snapshot = _snapshot(
        2,
        workspaces=[_workspace(revision=2, status='active')],
    )
    with pytest.raises(DirectoryProjectionUnavailableError, match='conflicting contents'):
        await service.apply_snapshot(stale_same_cursor_snapshot)
    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        execution = await session.get(WorkspaceExecutionState, WORKSPACE_UUID)
    assert workspace.status == 'archived'
    assert execution.write_fenced is True


async def test_each_replica_consumes_events_with_its_own_cursor(projection_context):
    application, session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000005',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    updated = _delta(workspaces=[_workspace(revision=2, name='Replica-safe Workspace')])
    first_provider = _Provider([_snapshot(1)], [batch], [updated])
    second_provider = _Provider([_snapshot(1)], [batch], [updated])
    first = DirectoryProjectionService(application, first_provider, INSTANCE_UUID)
    second = DirectoryProjectionService(application, second_provider, INSTANCE_UUID)
    await first.initialize()
    await second.initialize()

    await first.sync_once()
    await second.sync_once()
    await second.sync_once()

    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)
        inbox_rows = (await session.scalars(sqlalchemy.select(DirectoryProjectionInbox))).all()
    assert workspace.name == 'Replica-safe Workspace'
    assert state.cursor == 2
    assert len(inbox_rows) == 1
    assert first_provider.after_cursors == [1]
    assert second_provider.after_cursors == [1, 2]


async def test_snapshot_coverage_allows_lagging_replica_to_replay_receipts(projection_context):
    application, session_factory = projection_context
    event_two = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000008',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    event_three = DirectoryEvent(
        cursor=3,
        uuid='40000000-0000-0000-0000-000000000009',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=3,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 3},
        created_at=datetime.datetime(2026, 7, 24, 12, 3, tzinfo=datetime.UTC),
    )
    batch_two = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=3,
        events=[event_two],
    )
    batch_three = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=2,
        cursor=3,
        high_water_cursor=3,
        events=[event_three],
    )
    lagging_provider = _Provider(
        [_snapshot(1)],
        [batch_two, batch_three],
        [
            _delta(workspaces=[_workspace(revision=2, name='Intermediate Workspace')]),
            _delta(workspaces=[_workspace(revision=3, name='Current Workspace')]),
        ],
    )
    lagging = DirectoryProjectionService(application, lagging_provider, INSTANCE_UUID)
    leading = DirectoryProjectionService(
        application,
        _Provider([_snapshot(3, workspaces=[_workspace(revision=3, name='Current Workspace')])]),
        INSTANCE_UUID,
    )
    await lagging.initialize()
    await leading.initialize()

    await lagging.sync_once()
    await lagging.sync_once()
    lagging.require_ready()

    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        state = await session.get(DirectoryProjectionState, INSTANCE_UUID)
        inbox_rows = (
            await session.scalars(sqlalchemy.select(DirectoryProjectionInbox).order_by(DirectoryProjectionInbox.cursor))
        ).all()
    assert workspace.name == 'Current Workspace'
    assert state.cursor == 3
    assert state.snapshot_coverage_cursor == 3
    assert [row.cursor for row in inbox_rows] == [2, 3]
    assert lagging_provider.after_cursors == [1, 2]


async def test_initialize_retries_snapshot_superseded_by_another_replica(projection_context):
    application, _session_factory = projection_context
    leading = DirectoryProjectionService(
        application,
        _Provider([_snapshot(2)]),
        INSTANCE_UUID,
    )
    await leading.initialize()
    racing_provider = _Provider([_snapshot(1), _snapshot(2)])
    racing = DirectoryProjectionService(application, racing_provider, INSTANCE_UUID)

    await racing.initialize()
    await racing.sync_once()
    racing.require_ready()

    assert racing_provider.snapshot_calls == 2
    assert racing_provider.after_cursors == [2]


async def test_page_below_signed_high_water_does_not_renew_readiness(projection_context):
    application, _session_factory = projection_context
    monotonic = [10.0]
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000010',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=3,
        events=[event],
    )
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)], [batch], [_delta()]),
        INSTANCE_UUID,
        sync_interval_seconds=5,
        max_staleness_seconds=60,
        monotonic_time=lambda: monotonic[0],
    )
    await service.initialize()
    await service.sync_once()

    monotonic[0] = 70.0
    with pytest.raises(DirectoryProjectionUnavailableError, match='stale'):
        service.require_ready()


async def test_empty_page_cannot_hide_shared_projection_progress(projection_context):
    application, _session_factory = projection_context
    lagging = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
    )
    leading = DirectoryProjectionService(
        application,
        _Provider([_snapshot(2)]),
        INSTANCE_UUID,
    )
    await lagging.initialize()
    await leading.initialize()

    with pytest.raises(DirectoryProjectionUnavailableError, match='has not consumed'):
        await lagging.sync_once()


async def test_event_payload_revision_mismatch_fails_closed(projection_context):
    application, _session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000006',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 3},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)], [batch], [_delta()]),
        INSTANCE_UUID,
    )
    await service.initialize()

    with pytest.raises(DirectoryProjectionUnavailableError, match='conflicting revision'):
        await service.sync_once()


async def test_workspace_delta_older_than_event_fails_closed(projection_context):
    application, _session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000007',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=3,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 3},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)], [batch], [_delta(workspaces=[_workspace(revision=2)])]),
        INSTANCE_UUID,
    )
    await service.initialize()

    with pytest.raises(DirectoryProjectionUnavailableError, match='older'):
        await service.sync_once()


async def test_stale_workspace_tombstone_revision_fails_closed(projection_context):
    application, session_factory = projection_context
    event = DirectoryEvent(
        cursor=2,
        uuid='40000000-0000-0000-0000-000000000011',
        aggregate_uuid=WORKSPACE_UUID,
        event_type='directory.changed',
        revision=2,
        payload={'workspace_uuid': WORKSPACE_UUID, 'directory_revision': 2},
        created_at=datetime.datetime(2026, 7, 24, 12, 2, tzinfo=datetime.UTC),
    )
    batch = DirectoryEventBatch(
        instance_uuid=INSTANCE_UUID,
        after_cursor=1,
        cursor=2,
        high_water_cursor=2,
        events=[event],
    )
    service = DirectoryProjectionService(
        application,
        _Provider(
            [_snapshot(1, workspaces=[_workspace(revision=3)])],
            [batch],
            [_delta(workspaces=[])],
        ),
        INSTANCE_UUID,
    )
    await service.initialize()

    with pytest.raises(DirectoryProjectionUnavailableError, match='tombstone revision rolled back'):
        await service.sync_once()

    async with session_factory() as session:
        workspace = await session.get(Workspace, WORKSPACE_UUID)
        membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
        execution = await session.get(WorkspaceExecutionState, WORKSPACE_UUID)
    assert workspace.status == 'active'
    assert membership.status == 'active'
    assert execution.write_fenced is False


async def test_conflicting_account_projection_across_workspaces_fails_closed(projection_context):
    application, _session_factory = projection_context
    conflicting_member = DirectoryMember(
        membership_uuid=SECOND_MEMBERSHIP_UUID,
        account_uuid=ACCOUNT_UUID,
        normalized_email='owner@example.com',
        display_name='Workspace Owner',
        account_status='blocked',
        role='member',
        membership_status='active',
        projection_revision=99,
        joined_at=datetime.datetime(2026, 7, 24, tzinfo=datetime.UTC),
    )
    second_workspace = DirectoryWorkspace(
        uuid=SECOND_WORKSPACE_UUID,
        name='Second Workspace',
        slug='second-workspace',
        type='team',
        status='active',
        created_by_account_uuid=ACCOUNT_UUID,
        projection_revision=99,
        execution_generation=1,
        members=[conflicting_member],
    )
    snapshot = _snapshot(
        1,
        workspaces=[_workspace(revision=1), second_workspace],
    )
    service = DirectoryProjectionService(application, _Provider([snapshot]), INSTANCE_UUID)

    with pytest.raises(DirectoryProjectionUnavailableError, match='conflicting account projections'):
        await service.initialize()


async def test_account_projection_revision_advances_when_account_fields_change(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
    )
    await service.initialize()
    blocked_member = _member(revision=2).model_copy(update={'account_status': 'blocked'})
    blocked_workspace = _workspace(revision=2).model_copy(update={'members': (blocked_member,)})

    await service.apply_snapshot(_snapshot(2, workspaces=[blocked_workspace]))

    async with session_factory() as session:
        account = await session.scalar(sqlalchemy.select(User).where(User.uuid == ACCOUNT_UUID))
    assert account.status == 'disabled'
    assert account.projection_revision == 2


async def test_readiness_expires_on_monotonic_staleness(projection_context):
    application, _session_factory = projection_context
    monotonic = [10.0]
    service = DirectoryProjectionService(
        application,
        _Provider([_snapshot(1)]),
        INSTANCE_UUID,
        sync_interval_seconds=5,
        max_staleness_seconds=60,
        monotonic_time=lambda: monotonic[0],
    )
    await service.initialize()
    service.require_ready()

    monotonic[0] = 70.0
    with pytest.raises(DirectoryProjectionUnavailableError, match='stale'):
        service.require_ready()


async def test_snapshot_for_another_instance_is_rejected(projection_context):
    application, _session_factory = projection_context
    other = _snapshot(1).model_copy(update={'instance_uuid': 'other-instance'})
    service = DirectoryProjectionService(application, _Provider([other]), INSTANCE_UUID)

    with pytest.raises(DirectoryProjectionUnavailableError, match='another LangBot instance'):
        await service.initialize()


async def test_directory_revision_zero_membership_is_adopted(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(application, _Provider([_snapshot(1)]), INSTANCE_UUID)
    await service.initialize()

    async with session_factory() as session:
        async with session.begin():
            membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
            membership.role = 'viewer'
            membership.status = 'active'
            membership.projection_revision = 0

    projected_member = _member(revision=2).model_copy(update={'role': 'owner', 'membership_status': 'removed'})
    projected_workspace = _workspace(revision=2).model_copy(update={'members': (projected_member,)})
    await service.apply_snapshot(_snapshot(2, workspaces=[projected_workspace]))

    async with session_factory() as session:
        membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
    assert membership.source == 'cloud_projection'
    assert membership.role == 'owner'
    assert membership.status == 'removed'
    assert membership.projection_revision == 2


async def test_directory_revision_zero_membership_omitted_from_snapshot_is_removed(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(application, _Provider([_snapshot(1)]), INSTANCE_UUID)
    await service.initialize()

    historical_account_uuid = '20000000-0000-0000-0000-000000000099'
    async with session_factory() as session:
        async with session.begin():
            membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
            session.add(
                User(
                    uuid=historical_account_uuid,
                    user='Historical Space Member',
                    normalized_email='historical@example.com',
                    password='',
                    status='active',
                    source='cloud_projection',
                    projection_revision=1,
                    account_type='space',
                    space_account_uuid=historical_account_uuid,
                )
            )
            session.add(
                WorkspaceMembership(
                    uuid=SECOND_MEMBERSHIP_UUID,
                    workspace_uuid=WORKSPACE_UUID,
                    account_uuid=historical_account_uuid,
                    role='viewer',
                    status='active',
                    source='cloud_projection',
                    joined_at=membership.joined_at,
                    projection_revision=0,
                )
            )

    await service.apply_snapshot(_snapshot(2))

    async with session_factory() as session:
        historical = await session.get(WorkspaceMembership, SECOND_MEMBERSHIP_UUID)
    assert historical.status == 'removed'
    assert historical.projection_revision == 2


async def test_cloud_account_core_invitation_membership_survives_directory_omission(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(application, _Provider([_snapshot(1)]), INSTANCE_UUID)
    await service.initialize()

    invited_account_uuid = '20000000-0000-0000-0000-000000000098'
    async with session_factory() as session:
        async with session.begin():
            projected_membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
            session.add(
                User(
                    uuid=invited_account_uuid,
                    user='Invited Cloud Account',
                    normalized_email='invited-cloud@example.com',
                    password='',
                    status='active',
                    source='cloud_projection',
                    projection_revision=1,
                    account_type='space',
                    space_account_uuid=invited_account_uuid,
                )
            )
            session.add(
                WorkspaceMembership(
                    uuid=SECOND_MEMBERSHIP_UUID,
                    workspace_uuid=WORKSPACE_UUID,
                    account_uuid=invited_account_uuid,
                    role='viewer',
                    status='active',
                    source='local',
                    joined_at=projected_membership.joined_at,
                    projection_revision=0,
                )
            )

    await service.apply_snapshot(_snapshot(2))

    async with session_factory() as session:
        membership = await session.get(WorkspaceMembership, SECOND_MEMBERSHIP_UUID)
    assert membership.source == 'local'
    assert membership.status == 'active'
    assert membership.projection_revision == 0


async def test_directory_does_not_adopt_local_membership_with_different_uuid_for_same_cloud_account(projection_context):
    application, session_factory = projection_context
    service = DirectoryProjectionService(application, _Provider([_snapshot(1)]), INSTANCE_UUID)
    await service.initialize()

    async with session_factory() as session:
        async with session.begin():
            membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
            membership.uuid = SECOND_MEMBERSHIP_UUID
            membership.source = 'local'
            membership.projection_revision = 0

    projected_member = _member(revision=2).model_copy(update={'role': 'owner', 'membership_status': 'removed'})
    projected_workspace = _workspace(revision=2).model_copy(update={'members': (projected_member,)})
    await service.apply_snapshot(_snapshot(2, workspaces=[projected_workspace]))

    async with session_factory() as session:
        membership = await session.get(WorkspaceMembership, SECOND_MEMBERSHIP_UUID)
    assert membership.source == 'local'
    assert membership.role == 'developer'
    assert membership.status == 'active'
    assert membership.projection_revision == 0
