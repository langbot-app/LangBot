from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionSource,
    WorkspaceExecutionState,
    WorkspaceMembership,
    WorkspaceSource,
)
from langbot.pkg.workspace import (
    WorkspaceExecutionUnavailableError,
    WorkspaceExecutionBinding,
    WorkspaceGenerationMismatchError,
    WorkspaceInvariantError,
    WorkspaceLimitExceededError,
    WorkspaceNotFoundError,
    WorkspaceOwnerAlreadyExistsError,
    WorkspaceService,
)
from langbot.pkg.workspace.identity import workspace_uuid_from_instance_id
from langbot.pkg.workspace.policy import CloudWorkspacePolicy


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def workspace_test_context(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "workspace-service.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    persistence_mgr = SimpleNamespace(get_db_engine=lambda: engine)
    application = SimpleNamespace(persistence_mgr=persistence_mgr)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    service = WorkspaceService(application, instance_uuid='instance_service_test')
    yield service, session_factory
    await engine.dispose()


async def _insert_account(session, email: str) -> str:
    account_uuid = str(uuid.uuid4())
    session.add(
        User(
            uuid=account_uuid,
            user=email,
            normalized_email=email.strip().casefold(),
            password='hashed-password',
            account_type='local',
        )
    )
    await session.flush()
    return account_uuid


async def test_account_uuid_default_supports_existing_core_insert_path(workspace_test_context):
    _service, session_factory = workspace_test_context

    async with session_factory.begin() as session:
        await session.execute(
            sqlalchemy.insert(User).values(
                user='core-insert@example.com',
                normalized_email='core-insert@example.com',
                password='hashed-password',
                account_type='local',
            )
        )

    async with session_factory() as session:
        account = await session.scalar(sqlalchemy.select(User))
        assert account is not None
        uuid.UUID(account.uuid)
        assert account.status == 'active'
        assert account.source == 'local'


async def test_bootstrap_local_account_uses_callers_transaction(workspace_test_context):
    service, session_factory = workspace_test_context

    async with session_factory() as session:
        async with session.begin():
            account_uuid = await _insert_account(session, 'owner@example.com')
            workspace, membership = await service.bootstrap_local_account(account_uuid, session=session)
            assert session.in_transaction()
            assert workspace.created_by_account_uuid == account_uuid
            assert membership.account_uuid == account_uuid
            assert membership.role == 'owner'

    async with session_factory() as session:
        persisted_workspace = await session.scalar(sqlalchemy.select(Workspace))
        persisted_membership = await session.scalar(sqlalchemy.select(WorkspaceMembership))
        execution_state = await session.scalar(sqlalchemy.select(WorkspaceExecutionState))
        assert persisted_workspace is not None
        assert persisted_membership is not None
        assert execution_state is not None
        assert execution_state.workspace_uuid == persisted_workspace.uuid
        assert execution_state.instance_uuid == 'instance_service_test'
        assert execution_state.active_generation == 1
        assert execution_state.write_fenced is False


async def test_ensure_singleton_workspace_is_idempotent(workspace_test_context):
    service, session_factory = workspace_test_context

    first = await service.ensure_singleton_workspace()
    second = await service.ensure_singleton_workspace()

    assert first.uuid == workspace_uuid_from_instance_id('instance_service_test')
    assert second.uuid == first.uuid
    async with session_factory() as session:
        assert await session.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(Workspace)) == 1
        assert (
            await session.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(WorkspaceExecutionState)) == 1
        )


async def test_create_local_workspace_rejects_second_workspace(workspace_test_context):
    service, session_factory = workspace_test_context

    await service.create_local_workspace(name='First', slug='first')
    with pytest.raises(WorkspaceLimitExceededError) as exc_info:
        await service.create_local_workspace(name='Second', slug='second')

    assert exc_info.value.code == 'edition_limit'
    async with session_factory() as session:
        assert await session.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(Workspace)) == 1


async def test_initial_owner_cannot_be_claimed_by_another_account(workspace_test_context):
    service, session_factory = workspace_test_context

    async with session_factory() as session:
        async with session.begin():
            first_account_uuid = await _insert_account(session, 'first@example.com')
            second_account_uuid = await _insert_account(session, 'second@example.com')
            await service.bootstrap_local_account(first_account_uuid, session=session)

    with pytest.raises(WorkspaceOwnerAlreadyExistsError):
        await service.claim_initial_owner(second_account_uuid)

    async with session_factory() as session:
        owners = (
            await session.scalars(sqlalchemy.select(WorkspaceMembership).where(WorkspaceMembership.role == 'owner'))
        ).all()
        assert len(owners) == 1
        assert owners[0].account_uuid == first_account_uuid
        assert owners[0].source == 'local'


async def test_claim_initial_owner_reclassifies_existing_membership_as_local(workspace_test_context):
    service, session_factory = workspace_test_context

    async with session_factory() as session:
        async with session.begin():
            account_uuid = await _insert_account(session, 'reclaimed@example.com')
            workspace = await service.ensure_singleton_workspace(session=session)
            session.add(
                WorkspaceMembership(
                    uuid='44444444-4444-4444-8444-444444444444',
                    workspace_uuid=workspace.uuid,
                    account_uuid=account_uuid,
                    role='viewer',
                    status='removed',
                    source='cloud_projection',
                    projection_revision=4,
                )
            )

    membership = await service.claim_initial_owner(account_uuid)

    assert membership.role == 'owner'
    assert membership.status == 'active'
    assert membership.source == 'local'


async def test_execution_binding_returns_persisted_generation(workspace_test_context):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()

    async with session_factory.begin() as session:
        execution_state = await session.get(WorkspaceExecutionState, workspace.uuid)
        execution_state.active_generation = 7

    binding = await service.get_local_execution_binding(
        workspace.uuid,
        expected_generation=7,
    )

    assert binding.instance_uuid == 'instance_service_test'
    assert binding.workspace_uuid == workspace.uuid
    assert binding.placement_generation == 7
    assert binding.state == 'active'
    assert binding.write_fenced is False

    with pytest.raises(WorkspaceGenerationMismatchError):
        await service.get_local_execution_binding(workspace.uuid, expected_generation=6)


async def test_execution_binding_fails_closed_when_fenced(workspace_test_context):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()

    async with session_factory.begin() as session:
        execution_state = await session.get(WorkspaceExecutionState, workspace.uuid)
        execution_state.write_fenced = True

    with pytest.raises(WorkspaceExecutionUnavailableError):
        await service.get_local_execution_context(workspace.uuid)


@pytest.mark.parametrize(
    ('model', 'changes', 'error'),
    [
        (Workspace, {'status': 'suspended'}, WorkspaceExecutionUnavailableError),
        (Workspace, {'instance_uuid': 'another-instance'}, WorkspaceInvariantError),
        (WorkspaceExecutionState, {'write_fenced': True}, WorkspaceExecutionUnavailableError),
        (WorkspaceExecutionState, {'active_generation': 2}, WorkspaceGenerationMismatchError),
        (WorkspaceExecutionState, {'instance_uuid': 'another-instance'}, WorkspaceInvariantError),
        (WorkspaceExecutionState, {'source': 'cloud'}, WorkspaceInvariantError),
        (WorkspaceExecutionState, None, WorkspaceExecutionUnavailableError),
    ],
)
async def test_execution_binding_observes_projection_changes(workspace_test_context, model, changes, error):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()
    assert (await service.get_execution_binding(workspace.uuid, expected_generation=1)).placement_generation == 1

    key = Workspace.uuid if model is Workspace else WorkspaceExecutionState.workspace_uuid
    statement = sqlalchemy.delete(model) if changes is None else sqlalchemy.update(model).values(**changes)
    async with session_factory.begin() as session:
        await session.execute(statement.where(key == workspace.uuid))

    with pytest.raises(error):
        await service.get_execution_binding(workspace.uuid, expected_generation=1)


@pytest.mark.parametrize(
    ('changes', 'error'),
    [
        ({'write_fenced': True}, WorkspaceExecutionUnavailableError),
        ({'active_generation': 2}, WorkspaceGenerationMismatchError),
    ],
)
async def test_execution_binding_observes_unflushed_projection_changes(workspace_test_context, changes, error):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()
    async with session_factory.begin() as session:
        state = await session.get(WorkspaceExecutionState, workspace.uuid)
        for name, value in changes.items():
            setattr(state, name, value)
        with pytest.raises(error):
            await service.get_execution_binding(workspace.uuid, expected_generation=1, session=session)


async def test_execution_binding_does_not_lock_unrelated_pending_writes(workspace_test_context):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()
    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.exec_driver_sql('PRAGMA journal_mode=WAL')
    writer_engine = create_async_engine(engine.url, connect_args={'timeout': 0.05})
    writer_factory = async_sessionmaker(writer_engine, expire_on_commit=False)
    try:
        async with session_factory.begin() as session:
            directory = [
                await session.get(Workspace, workspace.uuid),
                await session.get(WorkspaceExecutionState, workspace.uuid),
            ]
            pending_account = User(
                uuid=str(uuid.uuid4()),
                user='pending@example.com',
                normalized_email='pending@example.com',
                password='hashed-password',
                account_type='local',
            )
            session.add(pending_account)
            binding = await service.get_execution_binding(workspace.uuid, expected_generation=1, session=session)
            assert binding.placement_generation == 1
            assert pending_account in session.new
            async with writer_factory.begin() as writer:
                await _insert_account(writer, 'independent@example.com')
            assert all(directory)
    finally:
        await writer_engine.dispose()


@pytest.mark.parametrize(
    ('changes', 'error'),
    [
        ({'write_fenced': True}, WorkspaceExecutionUnavailableError),
        ({'active_generation': 2}, WorkspaceGenerationMismatchError),
    ],
)
async def test_execution_binding_keeps_external_updates_over_stale_orm_values(workspace_test_context, changes, error):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()
    async with session_factory() as session:
        state = await session.get(WorkspaceExecutionState, workspace.uuid)
        state.desired_state_revision = 1
        async with session_factory.begin() as writer:
            await writer.execute(
                sqlalchemy.update(WorkspaceExecutionState)
                .where(WorkspaceExecutionState.workspace_uuid == workspace.uuid)
                .values(**changes)
            )
        with pytest.raises(error):
            await service.get_execution_binding(workspace.uuid, expected_generation=1, session=session)
        assert state in session.dirty
        assert state.write_fenced is False
        assert state.active_generation == 1


@pytest.mark.parametrize('model', [Workspace, WorkspaceExecutionState])
async def test_execution_binding_rejects_unflushed_directory_deletion(workspace_test_context, model):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()
    async with session_factory() as session:
        entity = await session.get(model, workspace.uuid)
        await session.delete(entity)
        error = WorkspaceNotFoundError if model is Workspace else WorkspaceExecutionUnavailableError
        with pytest.raises(error):
            await service.get_execution_binding(workspace.uuid, expected_generation=1, session=session)
        assert entity in session.deleted


async def test_execution_binding_does_not_publish_new_execution_state(workspace_test_context):
    service, session_factory = workspace_test_context
    workspace = await service.ensure_singleton_workspace()
    async with session_factory.begin() as session:
        await session.execute(
            sqlalchemy.delete(WorkspaceExecutionState).where(WorkspaceExecutionState.workspace_uuid == workspace.uuid)
        )
    async with session_factory() as session:
        state = WorkspaceExecutionState(
            workspace_uuid=workspace.uuid,
            instance_uuid=service.instance_uuid,
            active_generation=1,
            state='active',
            write_fenced=False,
            source='local',
            desired_state_revision=0,
        )
        session.add(state)
        with pytest.raises(WorkspaceExecutionUnavailableError):
            await service.get_execution_binding(workspace.uuid, expected_generation=1, session=session)
        assert state in session.new


async def test_execution_binding_does_not_publish_new_workspace(workspace_test_context):
    service, session_factory = workspace_test_context
    workspace = service._new_local_workspace(name='Pending', slug='pending')
    async with session_factory() as session:
        session.add(workspace)
        with pytest.raises(WorkspaceNotFoundError):
            await service.get_execution_binding(workspace.uuid, expected_generation=1, session=session)
        assert workspace in session.new


async def test_cloud_projection_requires_explicit_general_binding(workspace_test_context):
    service, session_factory = workspace_test_context
    await service.ensure_singleton_workspace()
    cloud_workspace_uuid = str(uuid.uuid4())

    async with session_factory.begin() as session:
        session.add(
            Workspace(
                uuid=cloud_workspace_uuid,
                instance_uuid='instance_service_test',
                name='Cloud Workspace',
                slug='cloud-workspace',
                source=WorkspaceSource.CLOUD_PROJECTION.value,
            )
        )
        session.add(
            WorkspaceExecutionState(
                workspace_uuid=cloud_workspace_uuid,
                instance_uuid='instance_service_test',
                active_generation=9,
                state='active',
                write_fenced=False,
                source=WorkspaceExecutionSource.CLOUD.value,
            )
        )

    binding = await service.get_execution_binding(
        cloud_workspace_uuid,
        expected_generation=9,
    )
    assert binding.workspace_uuid == cloud_workspace_uuid
    assert binding.placement_generation == 9

    with pytest.raises(WorkspaceInvariantError):
        await service.get_local_execution_binding(cloud_workspace_uuid)


async def test_cloud_policy_never_creates_or_guesses_a_workspace(workspace_test_context):
    service, _session_factory = workspace_test_context
    cloud_service = WorkspaceService(
        service.ap,
        policy=CloudWorkspacePolicy(),
        instance_uuid='instance_service_test',
    )

    with pytest.raises(WorkspaceLimitExceededError):
        await cloud_service.create_local_workspace(name='Forbidden', slug='forbidden')

    assert cloud_service.policy.multi_workspace_enabled is True


async def test_startup_binding_snapshot_avoids_repeated_discovery():
    service = WorkspaceService(
        SimpleNamespace(persistence_mgr=SimpleNamespace()),
        policy=CloudWorkspacePolicy(),
        instance_uuid='instance-service-test',
    )
    binding = WorkspaceExecutionBinding(
        instance_uuid='instance-service-test',
        workspace_uuid='workspace-a',
        placement_generation=1,
        write_fenced=False,
        state='active',
    )
    service._discover_active_execution_bindings = AsyncMock(return_value=[binding])

    assert await service.prime_startup_execution_bindings() == [binding]
    assert await service.list_active_execution_bindings() == [binding]
    assert await service.list_active_execution_bindings() == [binding]
    service._discover_active_execution_bindings.assert_awaited_once()

    service.release_startup_execution_bindings()
    assert await service.list_active_execution_bindings() == [binding]
    assert service._discover_active_execution_bindings.await_count == 2
