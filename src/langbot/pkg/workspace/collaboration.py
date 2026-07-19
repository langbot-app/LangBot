from __future__ import annotations

import dataclasses
import datetime
import hashlib
import secrets
import typing
import uuid
import asyncio
from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..entity.persistence.user import AccountStatus, User
from ..entity.persistence.workspace import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
    WorkspaceSource,
    WorkspaceStatus,
)
from .entities import WorkspaceExecutionBinding
from .errors import WorkspaceNotFoundError
from .policy import CloudWorkspacePolicy, SingleWorkspacePolicy
from .service import WorkspaceService

if typing.TYPE_CHECKING:
    from ..core.app import Application


class WorkspaceCollaborationError(Exception):
    """Stable collaboration error surfaced by the Workspace API."""

    code = 'workspace_collaboration_error'


class MembershipNotFoundError(WorkspaceCollaborationError):
    code = 'membership_not_found'


class MembershipPermissionError(WorkspaceCollaborationError):
    code = 'permission_denied'


class LastOwnerError(WorkspaceCollaborationError):
    code = 'last_owner_required'


class InvitationError(WorkspaceCollaborationError):
    code = 'invitation_invalid'


class InvitationExpiredError(InvitationError):
    code = 'invitation_expired'


class InvitationRevokedError(InvitationError):
    code = 'invitation_revoked'


class InvitationUsedError(InvitationError):
    code = 'invitation_used'


class InvitationEmailMismatchError(InvitationError):
    code = 'invitation_email_mismatch'


class InvitationRoleError(InvitationError):
    code = 'invitation_role_invalid'


class AlreadyMemberError(InvitationError):
    code = 'already_a_member'


@dataclasses.dataclass(frozen=True, slots=True)
class ResolvedWorkspaceAccess:
    workspace: Workspace
    membership: WorkspaceMembership
    execution: WorkspaceExecutionBinding


@dataclasses.dataclass(frozen=True, slots=True)
class WorkspaceMemberView:
    membership: WorkspaceMembership
    email: str


@dataclasses.dataclass(frozen=True, slots=True)
class CreatedInvitation:
    invitation: WorkspaceInvitation
    token: str


@dataclasses.dataclass(slots=True)
class _InvitationLockEntry:
    lock: asyncio.Lock
    users: int = 0


T = typing.TypeVar('T')


def normalize_email(email: str) -> str:
    """Return the canonical email identity used by invitations."""

    normalized = email.strip().casefold()
    if not normalized or '@' not in normalized:
        raise ValueError('A valid email address is required')
    if len(normalized) > 320:
        raise ValueError('Email address exceeds the normalized identity limit')
    return normalized


def hash_invitation_token(token: str) -> str:
    """Hash an invitation bearer secret for lookup and at-rest storage."""

    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class WorkspaceCollaborationService:
    """Membership and invitation operations for the local Workspace directory."""

    def __init__(
        self,
        ap: Application,
        workspace_service: WorkspaceService,
        *,
        policy: SingleWorkspacePolicy | CloudWorkspacePolicy | None = None,
    ) -> None:
        self.ap = ap
        self.workspace_service = workspace_service
        self.policy = policy or workspace_service.policy
        self._invitation_locks: dict[str, _InvitationLockEntry] = {}
        self._invitation_locks_guard = asyncio.Lock()

    def _session_factory(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            self.ap.persistence_mgr.get_db_engine(),
            expire_on_commit=False,
        )

    async def resolve_account_workspace(
        self,
        account_uuid: str,
        requested_workspace_uuid: str | None,
        *,
        session: AsyncSession | None = None,
    ) -> ResolvedWorkspaceAccess:
        """Resolve a selector against an active Account membership."""

        async def operation(active_session: AsyncSession) -> ResolvedWorkspaceAccess:
            workspace_uuid = requested_workspace_uuid.strip() if requested_workspace_uuid else None
            if workspace_uuid is None:
                if self.policy.multi_workspace_enabled:
                    raise WorkspaceNotFoundError('A Workspace selector is required')
                workspace = await self.workspace_service.get_singleton_workspace(session=active_session)
            else:
                workspace = await active_session.get(Workspace, workspace_uuid)
                if (
                    workspace is None
                    or workspace.instance_uuid != self.workspace_service.instance_uuid
                    or workspace.status != WorkspaceStatus.ACTIVE.value
                ):
                    raise WorkspaceNotFoundError('Workspace not found')

            membership = await active_session.scalar(
                sqlalchemy.select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_uuid == workspace.uuid,
                    WorkspaceMembership.account_uuid == account_uuid,
                    WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                )
            )
            if membership is None:
                # Deliberately hide Workspace existence across Accounts.
                raise WorkspaceNotFoundError('Workspace not found')

            execution = await self.workspace_service.get_execution_binding(
                workspace.uuid,
                session=active_session,
            )
            return ResolvedWorkspaceAccess(workspace, membership, execution)

        return await self._run(operation, session=session, read_only=True)

    async def list_account_workspaces(
        self,
        account_uuid: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ResolvedWorkspaceAccess]:
        async def operation(active_session: AsyncSession) -> list[ResolvedWorkspaceAccess]:
            statement = (
                sqlalchemy.select(WorkspaceMembership, Workspace)
                .join(Workspace, Workspace.uuid == WorkspaceMembership.workspace_uuid)
                .where(
                    WorkspaceMembership.account_uuid == account_uuid,
                    WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                    Workspace.instance_uuid == self.workspace_service.instance_uuid,
                    Workspace.status == WorkspaceStatus.ACTIVE.value,
                )
                .order_by(Workspace.created_at, Workspace.uuid)
            )
            rows = (await active_session.execute(statement)).all()
            accesses: list[ResolvedWorkspaceAccess] = []
            for membership, workspace in rows:
                execution = await self.workspace_service.get_execution_binding(
                    workspace.uuid,
                    session=active_session,
                )
                accesses.append(ResolvedWorkspaceAccess(workspace, membership, execution))
            return accesses

        return await self._run(operation, session=session, read_only=True)

    async def list_members(
        self,
        workspace_uuid: str,
        actor: WorkspaceMembership,
        *,
        session: AsyncSession | None = None,
    ) -> list[WorkspaceMemberView]:
        async def operation(active_session: AsyncSession) -> list[WorkspaceMemberView]:
            await self._load_actor(active_session, workspace_uuid, actor)
            statement = (
                sqlalchemy.select(WorkspaceMembership, User.user)
                .join(User, User.uuid == WorkspaceMembership.account_uuid)
                .where(
                    WorkspaceMembership.workspace_uuid == workspace_uuid,
                    WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                    User.status == AccountStatus.ACTIVE.value,
                )
                .order_by(WorkspaceMembership.created_at, WorkspaceMembership.uuid)
            )
            return [
                WorkspaceMemberView(membership=membership, email=email)
                for membership, email in (await active_session.execute(statement)).all()
            ]

        return await self._run(operation, session=session, read_only=True)

    async def list_invitations(
        self,
        workspace_uuid: str,
        actor: WorkspaceMembership,
        *,
        session: AsyncSession | None = None,
    ) -> list[WorkspaceInvitation]:
        async def operation(active_session: AsyncSession) -> list[WorkspaceInvitation]:
            await self._require_local_workspace(active_session, workspace_uuid)
            persisted_actor = await self._load_actor(active_session, workspace_uuid, actor)
            self._require_member_manager(persisted_actor, workspace_uuid)
            await self._expire_pending_invitations(active_session, workspace_uuid=workspace_uuid)
            statement = (
                sqlalchemy.select(WorkspaceInvitation)
                .where(
                    WorkspaceInvitation.workspace_uuid == workspace_uuid,
                    WorkspaceInvitation.status == InvitationStatus.PENDING.value,
                )
                .order_by(WorkspaceInvitation.created_at, WorkspaceInvitation.uuid)
            )
            return list((await active_session.scalars(statement)).all())

        return await self._run(operation, session=session)

    async def create_invitation(
        self,
        workspace_uuid: str,
        actor: WorkspaceMembership,
        email: str,
        role: str,
        *,
        expires_in: datetime.timedelta = datetime.timedelta(days=7),
        session: AsyncSession | None = None,
    ) -> CreatedInvitation:
        if role not in {
            MembershipRole.ADMIN.value,
            MembershipRole.DEVELOPER.value,
            MembershipRole.OPERATOR.value,
            MembershipRole.VIEWER.value,
        }:
            raise InvitationRoleError('Invitations cannot grant this role')
        normalized_email = normalize_email(email)
        if expires_in <= datetime.timedelta(0):
            raise InvitationError('Invitation expiry must be in the future')

        async def operation(active_session: AsyncSession) -> CreatedInvitation:
            await self._require_local_workspace(active_session, workspace_uuid)
            persisted_actor = await self._load_actor(active_session, workspace_uuid, actor, for_update=True)
            self._require_member_manager(persisted_actor, workspace_uuid)
            existing_account = await active_session.scalar(
                sqlalchemy.select(User).where(User.normalized_email == normalized_email)
            )
            if existing_account is not None:
                existing_membership = await active_session.scalar(
                    sqlalchemy.select(WorkspaceMembership).where(
                        WorkspaceMembership.workspace_uuid == workspace_uuid,
                        WorkspaceMembership.account_uuid == existing_account.uuid,
                        WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                    )
                )
                if existing_membership is not None:
                    raise AlreadyMemberError('This Account is already a Workspace member')

            existing_pending = await active_session.scalar(
                sqlalchemy.select(WorkspaceInvitation)
                .where(
                    WorkspaceInvitation.workspace_uuid == workspace_uuid,
                    WorkspaceInvitation.normalized_email == normalized_email,
                    WorkspaceInvitation.status == InvitationStatus.PENDING.value,
                )
                .with_for_update()
            )
            now = self._utcnow()
            if existing_pending is not None:
                existing_pending.status = InvitationStatus.REVOKED.value
                existing_pending.revoked_at = now
                await active_session.flush()

            token = f'lbi_{secrets.token_urlsafe(32)}'
            invitation = WorkspaceInvitation(
                uuid=str(uuid.uuid4()),
                workspace_uuid=workspace_uuid,
                normalized_email=normalized_email,
                role=role,
                token_hash=hash_invitation_token(token),
                status=InvitationStatus.PENDING.value,
                expires_at=now + expires_in,
                created_by_account_uuid=persisted_actor.account_uuid,
            )
            active_session.add(invitation)
            await active_session.flush()
            return CreatedInvitation(invitation, token)

        return await self._run(operation, session=session)

    async def inspect_invitation(
        self,
        token: str,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[WorkspaceInvitation, Workspace]:
        async def operation(active_session: AsyncSession) -> tuple[WorkspaceInvitation, Workspace]:
            invitation = await self._get_invitation_by_token(active_session, token, for_update=True)
            self._validate_invitation_state(invitation)
            workspace = await active_session.get(Workspace, invitation.workspace_uuid)
            if workspace is None or workspace.status != WorkspaceStatus.ACTIVE.value:
                raise InvitationError('The invitation Workspace is unavailable')
            if workspace.source != WorkspaceSource.LOCAL.value:
                raise InvitationError('Cloud invitations are managed by the SaaS control plane')
            return invitation, workspace

        return await self._run(operation, session=session)

    async def accept_invitation(
        self,
        token: str,
        account_uuid: str,
        *,
        session: AsyncSession | None = None,
    ) -> WorkspaceMembership:
        async def operation(active_session: AsyncSession) -> WorkspaceMembership:
            invitation = await self._get_invitation_by_token(active_session, token, for_update=True)
            self._validate_invitation_state(invitation)
            await self._require_local_workspace(active_session, invitation.workspace_uuid)
            account = await active_session.scalar(sqlalchemy.select(User).where(User.uuid == account_uuid))
            if account is None or account.status != AccountStatus.ACTIVE.value:
                raise MembershipNotFoundError('Account not found')
            if account.normalized_email != invitation.normalized_email:
                raise InvitationEmailMismatchError('Invitation email does not match the Account')

            membership = await active_session.scalar(
                sqlalchemy.select(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_uuid == invitation.workspace_uuid,
                    WorkspaceMembership.account_uuid == account_uuid,
                )
                .with_for_update()
            )
            now = self._utcnow()
            if membership is None:
                membership = WorkspaceMembership(
                    uuid=str(uuid.uuid4()),
                    workspace_uuid=invitation.workspace_uuid,
                    account_uuid=account_uuid,
                    role=invitation.role,
                    status=MembershipStatus.ACTIVE.value,
                    invited_by_account_uuid=invitation.created_by_account_uuid,
                    joined_at=now,
                    projection_revision=0,
                )
                active_session.add(membership)
            elif membership.status != MembershipStatus.ACTIVE.value:
                membership.role = invitation.role
                membership.status = MembershipStatus.ACTIVE.value
                membership.invited_by_account_uuid = invitation.created_by_account_uuid
                membership.joined_at = now

            invitation.status = InvitationStatus.ACCEPTED.value
            invitation.accepted_at = now
            await active_session.flush()
            return membership

        token_digest = hash_invitation_token(token)
        async with self._invitation_lock(token_digest):
            return await self._run(operation, session=session)

    @asynccontextmanager
    async def _invitation_lock(self, token_digest: str):
        """Serialize one token while retaining only active lock entries."""

        async with self._invitation_locks_guard:
            entry = self._invitation_locks.get(token_digest)
            if entry is None:
                entry = _InvitationLockEntry(lock=asyncio.Lock())
                self._invitation_locks[token_digest] = entry
            entry.users += 1

        await entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            async with self._invitation_locks_guard:
                entry.users -= 1
                if entry.users == 0:
                    self._invitation_locks.pop(token_digest, None)

    async def revoke_invitation(
        self,
        workspace_uuid: str,
        invitation_uuid: str,
        actor: WorkspaceMembership,
        *,
        session: AsyncSession | None = None,
    ) -> WorkspaceInvitation:
        async def operation(active_session: AsyncSession) -> WorkspaceInvitation:
            await self._require_local_workspace(active_session, workspace_uuid)
            persisted_actor = await self._load_actor(active_session, workspace_uuid, actor, for_update=True)
            self._require_member_manager(persisted_actor, workspace_uuid)
            invitation = await active_session.scalar(
                sqlalchemy.select(WorkspaceInvitation)
                .where(
                    WorkspaceInvitation.uuid == invitation_uuid,
                    WorkspaceInvitation.workspace_uuid == workspace_uuid,
                )
                .with_for_update()
            )
            if invitation is None:
                raise InvitationError('Invitation not found')
            if invitation.status == InvitationStatus.REVOKED.value:
                return invitation
            if invitation.status != InvitationStatus.PENDING.value:
                self._validate_invitation_state(invitation)
            invitation.status = InvitationStatus.REVOKED.value
            invitation.revoked_at = self._utcnow()
            await active_session.flush()
            return invitation

        return await self._run(operation, session=session)

    async def update_member_role(
        self,
        workspace_uuid: str,
        target_account_uuid: str,
        role: str,
        actor: WorkspaceMembership,
        *,
        session: AsyncSession | None = None,
    ) -> WorkspaceMembership:
        if role not in {item.value for item in MembershipRole}:
            raise MembershipPermissionError('Unknown Workspace role')

        async def operation(active_session: AsyncSession) -> WorkspaceMembership:
            await self._require_local_workspace(active_session, workspace_uuid)
            persisted_actor = await self._load_actor(active_session, workspace_uuid, actor, for_update=True)
            self._require_member_manager(persisted_actor, workspace_uuid)
            target = await self._get_active_member_for_update(
                active_session,
                workspace_uuid,
                target_account_uuid,
            )
            self._require_can_manage_target(persisted_actor, target, new_role=role)
            if target.role == MembershipRole.OWNER.value and role != MembershipRole.OWNER.value:
                await self._require_another_owner(active_session, workspace_uuid, target.account_uuid)
            target.role = role
            await active_session.flush()
            return target

        return await self._run(operation, session=session)

    async def remove_member(
        self,
        workspace_uuid: str,
        target_account_uuid: str,
        actor: WorkspaceMembership,
        *,
        session: AsyncSession | None = None,
    ) -> WorkspaceMembership:
        async def operation(active_session: AsyncSession) -> WorkspaceMembership:
            await self._require_local_workspace(active_session, workspace_uuid)
            persisted_actor = await self._load_actor(active_session, workspace_uuid, actor, for_update=True)
            self._require_member_manager(persisted_actor, workspace_uuid)
            target = await self._get_active_member_for_update(
                active_session,
                workspace_uuid,
                target_account_uuid,
            )
            self._require_can_manage_target(persisted_actor, target)
            if target.role == MembershipRole.OWNER.value:
                await self._require_another_owner(active_session, workspace_uuid, target.account_uuid)
            target.status = MembershipStatus.REMOVED.value
            await active_session.flush()
            return target

        return await self._run(operation, session=session)

    async def _get_invitation_by_token(
        self,
        session: AsyncSession,
        token: str,
        *,
        for_update: bool,
    ) -> WorkspaceInvitation:
        if not isinstance(token, str) or not token.startswith('lbi_'):
            raise InvitationError('Invitation not found')
        statement = sqlalchemy.select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == hash_invitation_token(token)
        )
        if for_update:
            statement = statement.with_for_update()
        invitation = await session.scalar(statement)
        if invitation is None:
            raise InvitationError('Invitation not found')
        return invitation

    async def _require_local_workspace(
        self,
        session: AsyncSession,
        workspace_uuid: str,
    ) -> Workspace:
        workspace = await session.get(Workspace, workspace_uuid)
        if (
            workspace is None
            or workspace.instance_uuid != self.workspace_service.instance_uuid
            or workspace.status != WorkspaceStatus.ACTIVE.value
        ):
            raise WorkspaceNotFoundError('Workspace not found')
        if workspace.source != WorkspaceSource.LOCAL.value:
            raise MembershipPermissionError('Cloud Workspace directory changes are managed by the SaaS control plane')
        return workspace

    def _validate_invitation_state(self, invitation: WorkspaceInvitation) -> None:
        if invitation.status == InvitationStatus.REVOKED.value:
            raise InvitationRevokedError('Invitation was revoked')
        if invitation.status == InvitationStatus.ACCEPTED.value:
            raise InvitationUsedError('Invitation was already accepted')
        if invitation.status == InvitationStatus.EXPIRED.value or invitation.expires_at <= self._utcnow():
            invitation.status = InvitationStatus.EXPIRED.value
            raise InvitationExpiredError('Invitation has expired')
        if invitation.status != InvitationStatus.PENDING.value:
            raise InvitationError('Invitation is not pending')

    async def _expire_pending_invitations(
        self,
        session: AsyncSession,
        *,
        workspace_uuid: str,
    ) -> None:
        await session.execute(
            sqlalchemy.update(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_uuid == workspace_uuid,
                WorkspaceInvitation.status == InvitationStatus.PENDING.value,
                WorkspaceInvitation.expires_at <= self._utcnow(),
            )
            .values(status=InvitationStatus.EXPIRED.value)
        )

    async def _get_active_member_for_update(
        self,
        session: AsyncSession,
        workspace_uuid: str,
        account_uuid: str,
    ) -> WorkspaceMembership:
        membership = await session.scalar(
            sqlalchemy.select(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_uuid == workspace_uuid,
                WorkspaceMembership.account_uuid == account_uuid,
                WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
            )
            .with_for_update()
        )
        if membership is None:
            raise MembershipNotFoundError('Workspace member not found')
        return membership

    async def _load_actor(
        self,
        session: AsyncSession,
        workspace_uuid: str,
        actor: WorkspaceMembership,
        *,
        for_update: bool = False,
    ) -> WorkspaceMembership:
        self._require_actor_workspace(actor, workspace_uuid)
        statement = sqlalchemy.select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_uuid == workspace_uuid,
            WorkspaceMembership.account_uuid == actor.account_uuid,
            WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
        )
        if for_update:
            statement = statement.with_for_update()
        persisted_actor = await session.scalar(statement)
        if persisted_actor is None:
            raise WorkspaceNotFoundError('Workspace not found')
        return persisted_actor

    async def _require_another_owner(
        self,
        session: AsyncSession,
        workspace_uuid: str,
        excluded_account_uuid: str,
    ) -> None:
        owners = (
            await session.scalars(
                sqlalchemy.select(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_uuid == workspace_uuid,
                    WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
                    WorkspaceMembership.role == MembershipRole.OWNER.value,
                )
                .with_for_update()
            )
        ).all()
        if not any(owner.account_uuid != excluded_account_uuid for owner in owners):
            raise LastOwnerError('The last Workspace owner cannot be removed or demoted')

    def _require_actor_workspace(self, actor: WorkspaceMembership, workspace_uuid: str) -> None:
        if actor.workspace_uuid != workspace_uuid or actor.status != MembershipStatus.ACTIVE.value:
            raise WorkspaceNotFoundError('Workspace not found')

    def _require_member_manager(self, actor: WorkspaceMembership, workspace_uuid: str) -> None:
        self._require_actor_workspace(actor, workspace_uuid)
        if actor.role not in {MembershipRole.OWNER.value, MembershipRole.ADMIN.value}:
            raise MembershipPermissionError('Member management permission is required')

    def _require_can_manage_target(
        self,
        actor: WorkspaceMembership,
        target: WorkspaceMembership,
        *,
        new_role: str | None = None,
    ) -> None:
        if actor.role == MembershipRole.ADMIN.value and (
            target.role == MembershipRole.OWNER.value or new_role == MembershipRole.OWNER.value
        ):
            raise MembershipPermissionError('Admins cannot manage Workspace owners')

    @staticmethod
    def _utcnow() -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

    async def _run(
        self,
        operation: Callable[[AsyncSession], Awaitable[T]],
        *,
        session: AsyncSession | None,
        read_only: bool = False,
    ) -> T:
        if session is not None:
            return await operation(session)
        async with self._session_factory()() as owned_session:
            if read_only:
                return await operation(owned_session)
            async with owned_session.begin():
                return await operation(owned_session)
