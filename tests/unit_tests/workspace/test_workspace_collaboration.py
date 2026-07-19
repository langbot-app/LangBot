from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionState,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from langbot.pkg.workspace.collaboration import (
    InvitationEmailMismatchError,
    InvitationRoleError,
    InvitationUsedError,
    LastOwnerError,
    MembershipPermissionError,
    WorkspaceCollaborationService,
)
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from langbot.pkg.workspace.service import WorkspaceService
from langbot.pkg.workspace.policy import CloudWorkspacePolicy


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def collaboration_context(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "workspace-collaboration.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    persistence_mgr = SimpleNamespace(get_db_engine=lambda: engine)
    application = SimpleNamespace(persistence_mgr=persistence_mgr)
    workspace_service = WorkspaceService(application, instance_uuid='instance-collaboration-test')
    service = WorkspaceCollaborationService(application, workspace_service)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            owner = User(
                uuid=str(uuid.uuid4()),
                user='owner@example.com',
                normalized_email='owner@example.com',
                password='owner-hash',
                account_type='local',
            )
            session.add(owner)
            await session.flush()
            workspace, owner_membership = await workspace_service.bootstrap_local_account(
                owner.uuid,
                session=session,
            )

    yield service, workspace_service, session_factory, owner, workspace, owner_membership
    await engine.dispose()


async def _add_account(session_factory, email: str) -> User:
    async with session_factory() as session:
        async with session.begin():
            account = User(
                uuid=str(uuid.uuid4()),
                user=email,
                normalized_email=email.strip().casefold(),
                password='member-hash',
                account_type='local',
            )
            session.add(account)
            await session.flush()
            return account


async def test_invitation_secret_is_hashed_and_acceptance_is_one_time(collaboration_context):
    service, _, session_factory, _, workspace, owner_membership = collaboration_context
    created = await service.create_invitation(
        workspace.uuid,
        owner_membership,
        'member@example.com',
        'developer',
    )

    assert created.token.startswith('lbi_')
    assert created.invitation.token_hash != created.token
    assert created.token not in created.invitation.token_hash

    account = await _add_account(session_factory, 'MEMBER@example.com')
    membership = await service.accept_invitation(created.token, account.uuid)
    assert membership.workspace_uuid == workspace.uuid
    assert membership.role == 'developer'

    with pytest.raises(InvitationUsedError):
        await service.accept_invitation(created.token, account.uuid)

    async with session_factory() as session:
        persisted = await session.get(WorkspaceInvitation, created.invitation.uuid)
        assert persisted is not None
        assert persisted.status == 'accepted'
        assert not hasattr(persisted, 'token')


async def test_concurrent_invitation_acceptance_creates_one_membership(collaboration_context):
    service, _, session_factory, _, workspace, owner_membership = collaboration_context
    created = await service.create_invitation(
        workspace.uuid,
        owner_membership,
        'race@example.com',
        'viewer',
    )
    account = await _add_account(session_factory, 'race@example.com')

    results = await asyncio.gather(
        service.accept_invitation(created.token, account.uuid),
        service.accept_invitation(created.token, account.uuid),
        return_exceptions=True,
    )

    assert sum(isinstance(result, WorkspaceMembership) for result in results) == 1
    assert sum(isinstance(result, InvitationUsedError) for result in results) == 1
    async with session_factory() as session:
        count = await session.scalar(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_uuid == workspace.uuid,
                WorkspaceMembership.account_uuid == account.uuid,
            )
        )
        assert count == 1


async def test_invitation_rejects_owner_role_and_email_mismatch(collaboration_context):
    service, _, session_factory, _, workspace, owner_membership = collaboration_context
    with pytest.raises(InvitationRoleError):
        await service.create_invitation(
            workspace.uuid,
            owner_membership,
            'member@example.com',
            'owner',
        )

    created = await service.create_invitation(
        workspace.uuid,
        owner_membership,
        'expected@example.com',
        'viewer',
    )
    wrong_account = await _add_account(session_factory, 'wrong@example.com')
    with pytest.raises(InvitationEmailMismatchError):
        await service.accept_invitation(created.token, wrong_account.uuid)


async def test_last_owner_cannot_be_demoted(collaboration_context):
    service, _, session_factory, _, workspace, owner_membership = collaboration_context
    created = await service.create_invitation(
        workspace.uuid,
        owner_membership,
        'second@example.com',
        'admin',
    )
    second = await _add_account(session_factory, 'second@example.com')
    second_membership = await service.accept_invitation(created.token, second.uuid)

    with pytest.raises(LastOwnerError):
        await service.update_member_role(
            workspace.uuid,
            owner_membership.account_uuid,
            'admin',
            owner_membership,
        )

    with pytest.raises(MembershipPermissionError):
        await service.update_member_role(
            workspace.uuid,
            owner_membership.account_uuid,
            'viewer',
            second_membership,
        )

    promoted = await service.update_member_role(
        workspace.uuid,
        second.uuid,
        'owner',
        owner_membership,
    )
    assert promoted.role == 'owner'
    demoted = await service.update_member_role(
        workspace.uuid,
        owner_membership.account_uuid,
        'admin',
        owner_membership,
    )
    assert demoted.role == 'admin'


async def test_workspace_selector_requires_membership(collaboration_context):
    service, _, session_factory, _, workspace, _ = collaboration_context
    outsider = await _add_account(session_factory, 'outsider@example.com')

    with pytest.raises(WorkspaceNotFoundError):
        await service.resolve_account_workspace(outsider.uuid, workspace.uuid)


async def test_cloud_directory_requires_explicit_selector_and_rejects_local_mutation(
    collaboration_context,
):
    _service, workspace_service, session_factory, owner, _workspace, _membership = collaboration_context
    cloud_workspace_uuid = str(uuid.uuid4())
    cloud_membership = WorkspaceMembership(
        uuid=str(uuid.uuid4()),
        workspace_uuid=cloud_workspace_uuid,
        account_uuid=owner.uuid,
        role='owner',
        status='active',
        projection_revision=4,
    )
    async with session_factory.begin() as session:
        session.add(
            Workspace(
                uuid=cloud_workspace_uuid,
                instance_uuid='instance-collaboration-test',
                name='Projected Workspace',
                slug='projected-workspace',
                source='cloud_projection',
                projection_revision=4,
            )
        )
        session.add(
            WorkspaceExecutionState(
                workspace_uuid=cloud_workspace_uuid,
                instance_uuid='instance-collaboration-test',
                active_generation=8,
                state='active',
                write_fenced=False,
                source='cloud',
                desired_state_revision=8,
            )
        )
        session.add(cloud_membership)

    cloud_service = WorkspaceCollaborationService(
        workspace_service.ap,
        WorkspaceService(
            workspace_service.ap,
            policy=CloudWorkspacePolicy(),
            instance_uuid='instance-collaboration-test',
        ),
    )
    with pytest.raises(WorkspaceNotFoundError):
        await cloud_service.resolve_account_workspace(owner.uuid, None)

    access = await cloud_service.resolve_account_workspace(owner.uuid, cloud_workspace_uuid)
    assert access.workspace.uuid == cloud_workspace_uuid
    assert access.execution.placement_generation == 8

    with pytest.raises(MembershipPermissionError, match='control plane'):
        await cloud_service.create_invitation(
            cloud_workspace_uuid,
            cloud_membership,
            'member@example.com',
            'viewer',
        )


async def test_invitation_lock_registry_does_not_retain_sequential_tokens(collaboration_context):
    service, *_ = collaboration_context

    for index in range(100):
        async with service._invitation_lock(f'token-{index}'):
            pass

    assert service._invitation_locks == {}


async def test_invitation_lock_registry_keeps_waiters_serialized(collaboration_context):
    service, *_ = collaboration_context
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def first_worker() -> None:
        async with service._invitation_lock('same-token'):
            order.append('first')
            first_entered.set()
            await release_first.wait()

    async def second_worker() -> None:
        await first_entered.wait()
        async with service._invitation_lock('same-token'):
            order.append('second')

    first_task = asyncio.create_task(first_worker())
    second_task = asyncio.create_task(second_worker())
    await first_entered.wait()
    await asyncio.sleep(0)

    assert order == ['first']
    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert order == ['first', 'second']
    assert service._invitation_locks == {}
