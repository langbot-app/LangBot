"""Space-managed members for LangBot Cloud dedicated instances.

A dedicated instance runs Core in OSS mode with ``system.edition == 'cloud'``.
Its buyer manages invitations on LangBot Space, which is the only authority on
who else may enter. When a Space account signs in, Core asks Space for that
account's role on this instance (``instance_id`` is the Pod UUID) and mirrors
it into the singleton Workspace.

Compatibility rules:

* Nothing here runs outside ``edition == 'cloud'`` in OSS deployment mode, so
  self-hosted OSS and multi-workspace Cloud v2 never take these paths.
* Space never grants ``owner`` and Core never changes the local owner, local
  password accounts, or members who joined through local invitations. Only
  *Space-managed* accounts are reconciled: non-owner accounts bound to Space
  that have no local password. On an OSS-mode instance no other path creates
  such accounts, so existing password-initialized instances keep their users.
* A failed lookup (network, expired token) never removes anyone; only an
  explicit "not a member" answer from Space does.
"""

from __future__ import annotations

import datetime
import typing
import uuid

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..entity.persistence import user as user_entity
from ..entity.persistence.workspace import (
    MembershipRole,
    MembershipSource,
    MembershipStatus,
    WorkspaceMembership,
)
from ..utils import constants

if typing.TYPE_CHECKING:
    from ..core import app

SPACE_MEMBER_ROLES = frozenset(
    {
        MembershipRole.ADMIN.value,
        MembershipRole.DEVELOPER.value,
        MembershipRole.OPERATOR.value,
        MembershipRole.VIEWER.value,
    }
)


class SpaceMembershipLookupError(Exception):
    """Space could not answer; callers must not treat this as a revocation."""


def space_dedicated_members_enabled(ap: app.Application) -> bool:
    deployment_mode = getattr(getattr(ap, 'deployment', None), 'mode', 'oss')
    return constants.edition == 'cloud' and deployment_mode != 'cloud'


def is_space_managed_account(account: user_entity.User) -> bool:
    return bool(account.space_account_uuid) and not account.password


class SpaceDedicatedMembers:
    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    def enabled(self) -> bool:
        return space_dedicated_members_enabled(self.ap)

    def _session_factory(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(self.ap.persistence_mgr.get_db_engine(), expire_on_commit=False)

    async def lookup_role(self, access_token: str) -> str | None:
        """Return the account's non-owner role on this instance, or None.

        ``owner`` is reported as None: ownership is local and never mirrored.
        """
        try:
            data = await self.ap.space_service.get_dedicated_membership(access_token)
        except Exception as exc:
            raise SpaceMembershipLookupError(str(exc)) from exc
        role = str(data.get('role') or '')
        return role if role in SPACE_MEMBER_ROLES else None

    async def create_member_account(
        self,
        *,
        space_account_uuid: str,
        email: str,
        role: str,
        token_values: dict[str, typing.Any],
    ) -> user_entity.User:
        """Create a Space account and join it to the singleton Workspace."""
        if role not in SPACE_MEMBER_ROLES:
            raise ValueError('Space cannot grant this role')
        normalized = email.strip().lower()
        async with self._session_factory()() as session:
            async with session.begin():
                account = user_entity.User(
                    uuid=str(uuid.uuid4()),
                    user=normalized,
                    normalized_email=normalized,
                    password='',
                    account_type='space',
                    status=user_entity.AccountStatus.ACTIVE.value,
                    source=user_entity.AccountSource.LOCAL.value,
                    projection_revision=0,
                    space_account_uuid=space_account_uuid,
                    **token_values,
                )
                session.add(account)
                await session.flush()
                await self._apply_role(session, account.uuid, role)
        return account

    async def reconcile_account(self, account: user_entity.User, role: str | None) -> bool:
        """Mirror Space's answer for a Space-managed account.

        Returns False when the account no longer has access.
        """
        if not is_space_managed_account(account):
            return True
        async with self._session_factory()() as session:
            async with session.begin():
                return await self._apply_role(session, account.uuid, role)

    async def _apply_role(self, session: AsyncSession, account_uuid: str, role: str | None) -> bool:
        workspace = await self.ap.workspace_service.get_singleton_workspace(session=session)
        membership = await session.scalar(
            sqlalchemy.select(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_uuid == workspace.uuid,
                WorkspaceMembership.account_uuid == account_uuid,
            )
            .with_for_update()
        )
        if membership is not None and membership.role == MembershipRole.OWNER.value:
            # The local owner is never changed from Space.
            return True
        if role is None:
            if membership is not None and membership.status == MembershipStatus.ACTIVE.value:
                membership.status = MembershipStatus.REMOVED.value
                await session.flush()
            return False
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        if membership is None:
            session.add(
                WorkspaceMembership(
                    uuid=str(uuid.uuid4()),
                    workspace_uuid=workspace.uuid,
                    account_uuid=account_uuid,
                    role=role,
                    status=MembershipStatus.ACTIVE.value,
                    source=MembershipSource.LOCAL.value,
                    joined_at=now,
                    projection_revision=0,
                )
            )
        else:
            membership.role = role
            if membership.status != MembershipStatus.ACTIVE.value:
                membership.status = MembershipStatus.ACTIVE.value
                membership.joined_at = now
        await session.flush()
        return True

    async def sync_all(self) -> int:
        """Re-check every Space-managed member with that member's own token.

        Returns the number of accounts whose access was removed.
        """
        if not self.enabled():
            return 0
        async with self._session_factory()() as session:
            workspace = await self.ap.workspace_service.get_singleton_workspace(session=session)
            rows = (
                await session.execute(
                    sqlalchemy.select(user_entity.User)
                    .join(WorkspaceMembership, WorkspaceMembership.account_uuid == user_entity.User.uuid)
                    .where(
                        WorkspaceMembership.workspace_uuid == workspace.uuid,
                        WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                        WorkspaceMembership.role != MembershipRole.OWNER.value,
                        user_entity.User.space_account_uuid.is_not(None),
                    )
                )
            ).scalars()
            accounts = [account for account in rows if is_space_managed_account(account)]

        removed = 0
        for account in accounts:
            try:
                token = await self.ap.space_service.get_valid_access_token(account.user)
                if not token:
                    continue
                role = await self.lookup_role(token)
            except SpaceMembershipLookupError:
                continue
            if not await self.reconcile_account(account, role):
                removed += 1
        return removed
