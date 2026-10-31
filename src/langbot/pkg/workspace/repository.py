from __future__ import annotations

import typing

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


_WORKSPACE_COLUMNS = Workspace.__table__.c
_EXECUTION_COLUMNS = WorkspaceExecutionState.__table__.c
_EXECUTION_PROJECTION = (
    sqlalchemy.select(
        _WORKSPACE_COLUMNS.uuid,
        _WORKSPACE_COLUMNS.instance_uuid,
        _WORKSPACE_COLUMNS.source,
        _WORKSPACE_COLUMNS.status,
        _WORKSPACE_COLUMNS.created_at,
        _EXECUTION_COLUMNS.instance_uuid.label('execution_instance_uuid'),
        _EXECUTION_COLUMNS.active_generation,
        _EXECUTION_COLUMNS.state,
        _EXECUTION_COLUMNS.write_fenced,
        _EXECUTION_COLUMNS.source.label('execution_source'),
    )
    .outerjoin(WorkspaceExecutionState.__table__, _EXECUTION_COLUMNS.workspace_uuid == _WORKSPACE_COLUMNS.uuid)
    .where(_WORKSPACE_COLUMNS.uuid == sqlalchemy.bindparam('workspace_uuid'))
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

    async def get_execution_projection(self, workspace_uuid: str) -> dict[str, typing.Any] | None:
        """Read current fencing records without flushing caller-owned writes."""
        with self.session.no_autoflush:
            result = await self.session.execute(_EXECUTION_PROJECTION, {'workspace_uuid': workspace_uuid})
        row = result.mappings().first()
        if row is None:
            return None
        projection = dict(row)
        for entity in self.session.new | self.session.deleted:
            if isinstance(entity, Workspace) and (
                entity.uuid == workspace_uuid or sqlalchemy.inspect(entity).identity == (workspace_uuid,)
            ):
                # New and deleted directory records cannot authorize execution.
                return None
            if isinstance(entity, WorkspaceExecutionState) and (
                entity.workspace_uuid == workspace_uuid or sqlalchemy.inspect(entity).identity == (workspace_uuid,)
            ):
                projection['execution_instance_uuid'] = None
        for entity in self.session.dirty:
            if not isinstance(entity, (Workspace, WorkspaceExecutionState)):
                continue
            state = sqlalchemy.inspect(entity)
            if state.identity != (workspace_uuid,):
                continue
            identity_field = 'uuid' if isinstance(entity, Workspace) else 'workspace_uuid'
            if state.attrs[identity_field].history.has_changes():
                return None
            if isinstance(entity, Workspace):
                fields = {name: name for name in ('uuid', 'instance_uuid', 'source', 'status', 'created_at')}
            else:
                fields = {
                    'instance_uuid': 'execution_instance_uuid',
                    'active_generation': 'active_generation',
                    'state': 'state',
                    'write_fenced': 'write_fenced',
                    'source': 'execution_source',
                }
            for name, key in fields.items():
                history = state.attrs[name].history
                if history.has_changes():
                    projection[key] = history.added[0] if history.added else None
        return projection

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
