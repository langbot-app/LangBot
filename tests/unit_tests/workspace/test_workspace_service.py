from __future__ import annotations

import uuid
from types import SimpleNamespace

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
    WorkspaceGenerationMismatchError,
    WorkspaceInvariantError,
    WorkspaceLimitExceededError,
    WorkspaceOwnerAlreadyExistsError,
    WorkspaceService,
)
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
