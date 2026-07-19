from __future__ import annotations

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from ..entity.persistence.workspace import (
    MembershipRole,
    MembershipStatus,
    Workspace,
    WorkspaceExecutionState,
    WorkspaceMembership,
    WorkspaceSource,
)


class WorkspaceRepository:
    """Transaction-bound persistence operations for the workspace directory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_local_workspaces(self, instance_uuid: str) -> int:
        statement = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(Workspace)
            .where(
                Workspace.instance_uuid == instance_uuid,
                Workspace.source == WorkspaceSource.LOCAL.value,
            )
        )
        return int((await self.session.scalar(statement)) or 0)

    async def list_local_workspaces(self, instance_uuid: str, *, for_update: bool = False) -> list[Workspace]:
        statement = (
            sqlalchemy.select(Workspace)
            .where(
                Workspace.instance_uuid == instance_uuid,
                Workspace.source == WorkspaceSource.LOCAL.value,
            )
            .order_by(Workspace.created_at, Workspace.uuid)
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def get_workspace(self, workspace_uuid: str) -> Workspace | None:
        return await self.session.get(Workspace, workspace_uuid)

    def add_workspace(self, workspace: Workspace) -> None:
        self.session.add(workspace)

    async def get_execution_state(self, workspace_uuid: str) -> WorkspaceExecutionState | None:
        return await self.session.get(WorkspaceExecutionState, workspace_uuid)

    def add_execution_state(self, execution_state: WorkspaceExecutionState) -> None:
        self.session.add(execution_state)

    async def get_membership(self, workspace_uuid: str, account_uuid: str) -> WorkspaceMembership | None:
        statement = sqlalchemy.select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_uuid == workspace_uuid,
            WorkspaceMembership.account_uuid == account_uuid,
        )
        return await self.session.scalar(statement)

    async def get_active_owner(self, workspace_uuid: str, *, for_update: bool = False) -> WorkspaceMembership | None:
        statement = (
            sqlalchemy.select(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_uuid == workspace_uuid,
                WorkspaceMembership.role == MembershipRole.OWNER.value,
                WorkspaceMembership.status == MembershipStatus.ACTIVE.value,
            )
            .order_by(WorkspaceMembership.created_at, WorkspaceMembership.uuid)
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    def add_membership(self, membership: WorkspaceMembership) -> None:
        self.session.add(membership)

    async def flush(self) -> None:
        await self.session.flush()
