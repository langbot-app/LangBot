from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.errors.account import (
    SpaceAccountNotRegisteredError,
    SpaceDedicatedMemberRequiredError,
)
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import MembershipStatus, WorkspaceMembership
from langbot.pkg.utils import constants
from langbot.pkg.workspace.service import WorkspaceService
from langbot.pkg.workspace.space_dedicated import SpaceDedicatedMembers, space_dedicated_members_enabled


class _BufferedResult:
    """Rows buffered before the connection closes, like the real manager."""

    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0]


@pytest.fixture
async def dedicated_instance(tmp_path, monkeypatch):
    """A password-initialized dedicated instance (edition=cloud, OSS mode)."""
    monkeypatch.setattr(constants, 'edition', 'cloud')
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "dedicated.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    space_service = SimpleNamespace(
        get_dedicated_membership=AsyncMock(return_value={'role': ''}),
        get_valid_access_token=AsyncMock(return_value='member-token'),
    )

    async def execute_async(statement):
        async with engine.begin() as conn:
            result = await conn.execute(statement)
            if result.returns_rows:
                return _BufferedResult(result.fetchall())
            return result

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine, execute_async=execute_async),
        deployment=SimpleNamespace(mode='oss'),
        space_service=space_service,
        provider_service=SimpleNamespace(update_space_model_provider_api_keys=AsyncMock()),
        logger=SimpleNamespace(warning=lambda *a, **k: None, exception=lambda *a, **k: None),
    )
    workspace_service = WorkspaceService(ap, instance_uuid='dedicated-pod-uuid')
    ap.workspace_service = workspace_service
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        async with session.begin():
            owner = User(
                uuid=str(uuid.uuid4()),
                user='owner@example.com',
                normalized_email='owner@example.com',
                password='owner-password-hash',
                account_type='local',
            )
            session.add(owner)
            await session.flush()
            workspace, _ = await workspace_service.bootstrap_local_account(owner.uuid, session=session)

    service = UserService(ap)
    yield service, ap, sessions, owner, workspace
    await engine.dispose()


async def _membership(sessions, workspace_uuid: str, account_uuid: str) -> WorkspaceMembership | None:
    async with sessions() as session:
        return await session.scalar(
            sqlalchemy.select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_uuid == workspace_uuid,
                WorkspaceMembership.account_uuid == account_uuid,
            )
        )


async def _space_login(service: UserService, email: str = 'member@example.com', subject: str = 'space-member'):
    return await service.create_or_update_space_user(
        space_account_uuid=subject,
        email=email,
        access_token='access',
        refresh_token='refresh',
        api_key='key',
        expires_in=3600,
    )


def test_only_dedicated_cloud_instances_enable_space_members(monkeypatch):
    monkeypatch.setattr(constants, 'edition', 'community')
    assert not space_dedicated_members_enabled(SimpleNamespace(deployment=SimpleNamespace(mode='oss')))
    monkeypatch.setattr(constants, 'edition', 'cloud')
    assert space_dedicated_members_enabled(SimpleNamespace(deployment=SimpleNamespace(mode='oss')))
    # Cloud v2 (verified multi-workspace deployment) never uses this path.
    assert not space_dedicated_members_enabled(SimpleNamespace(deployment=SimpleNamespace(mode='cloud')))


async def test_uninvited_space_account_is_rejected(dedicated_instance):
    service, ap, *_ = dedicated_instance
    with pytest.raises(SpaceDedicatedMemberRequiredError):
        await _space_login(service)
    ap.space_service.get_dedicated_membership.assert_awaited_once_with('access')


async def test_space_outage_never_admits_a_new_account(dedicated_instance):
    service, ap, *_ = dedicated_instance
    ap.space_service.get_dedicated_membership.side_effect = RuntimeError('space down')
    with pytest.raises(SpaceDedicatedMemberRequiredError):
        await _space_login(service)


async def test_space_cannot_grant_owner(dedicated_instance):
    service, ap, *_ = dedicated_instance
    ap.space_service.get_dedicated_membership.return_value = {'role': 'owner'}
    with pytest.raises(SpaceDedicatedMemberRequiredError):
        await _space_login(service, email='other-owner@example.com', subject='other-owner')


async def test_invited_member_joins_then_follows_space(dedicated_instance):
    service, ap, sessions, owner, workspace = dedicated_instance
    ap.space_service.get_dedicated_membership.return_value = {'role': 'developer'}

    member = await _space_login(service)
    assert member.account_type == 'space' and not member.password
    membership = await _membership(sessions, workspace.uuid, member.uuid)
    assert membership.role == 'developer' and membership.status == MembershipStatus.ACTIVE.value

    # Role change on Space is mirrored at next login.
    ap.space_service.get_dedicated_membership.return_value = {'role': 'viewer'}
    await _space_login(service)
    assert (await _membership(sessions, workspace.uuid, member.uuid)).role == 'viewer'

    # A Space outage keeps current access.
    ap.space_service.get_dedicated_membership.side_effect = RuntimeError('space down')
    await _space_login(service)
    assert (await _membership(sessions, workspace.uuid, member.uuid)).status == MembershipStatus.ACTIVE.value
    ap.space_service.get_dedicated_membership.side_effect = None

    # Removal on Space is applied by the periodic sync without a new login.
    ap.space_service.get_dedicated_membership.return_value = {'role': ''}
    dedicated = SpaceDedicatedMembers(ap)
    assert await dedicated.sync_all() == 1
    assert (await _membership(sessions, workspace.uuid, member.uuid)).status == MembershipStatus.REMOVED.value
    with pytest.raises(SpaceDedicatedMemberRequiredError):
        await _space_login(service)

    # Re-inviting restores access.
    ap.space_service.get_dedicated_membership.return_value = {'role': 'operator'}
    await _space_login(service)
    restored = await _membership(sessions, workspace.uuid, member.uuid)
    assert restored.status == MembershipStatus.ACTIVE.value and restored.role == 'operator'

    # The password owner was never touched.
    owner_membership = await _membership(sessions, workspace.uuid, owner.uuid)
    assert owner_membership.role == 'owner' and owner_membership.status == MembershipStatus.ACTIVE.value


async def test_sync_never_touches_owner_or_local_accounts(dedicated_instance):
    service, ap, sessions, owner, workspace = dedicated_instance
    # A member who joined via a local (password) invitation and later bound Space.
    async with sessions() as session:
        async with session.begin():
            local_member = User(
                uuid=str(uuid.uuid4()),
                user='local@example.com',
                normalized_email='local@example.com',
                password='hash',
                account_type='local',
                space_account_uuid='space-local',
            )
            session.add(local_member)
            session.add(
                WorkspaceMembership(
                    uuid=str(uuid.uuid4()),
                    workspace_uuid=workspace.uuid,
                    account_uuid=local_member.uuid,
                    role='developer',
                    status=MembershipStatus.ACTIVE.value,
                    source='local',
                    projection_revision=0,
                )
            )
    ap.space_service.get_dedicated_membership.return_value = {'role': ''}
    assert await SpaceDedicatedMembers(ap).sync_all() == 0
    assert (await _membership(sessions, workspace.uuid, local_member.uuid)).status == MembershipStatus.ACTIVE.value
    assert (await _membership(sessions, workspace.uuid, owner.uuid)).status == MembershipStatus.ACTIVE.value


async def test_oss_community_keeps_original_rejection(dedicated_instance, monkeypatch):
    service, ap, *_ = dedicated_instance
    monkeypatch.setattr(constants, 'edition', 'community')
    with pytest.raises(SpaceAccountNotRegisteredError):
        await _space_login(service)
    ap.space_service.get_dedicated_membership.assert_not_awaited()
