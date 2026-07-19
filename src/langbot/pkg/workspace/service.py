from __future__ import annotations

import datetime
import uuid
import typing
from collections.abc import Awaitable, Callable
from typing import TypeVar

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..entity.persistence.workspace import (
    MembershipRole,
    MembershipStatus,
    Workspace,
    WorkspaceExecutionSource,
    WorkspaceExecutionState,
    WorkspaceExecutionStatus,
    WorkspaceMembership,
    WorkspaceSource,
    WorkspaceStatus,
    WorkspaceType,
)
from ..utils import constants
from .errors import (
    WorkspaceExecutionUnavailableError,
    WorkspaceGenerationMismatchError,
    WorkspaceInvariantError,
    WorkspaceNotFoundError,
    WorkspaceOwnerAlreadyExistsError,
)
from .entities import WorkspaceExecutionBinding
from .policy import CloudWorkspacePolicy, SingleWorkspacePolicy
from .repository import WorkspaceRepository


T = TypeVar('T')

if typing.TYPE_CHECKING:
    from ..core.app import Application


class WorkspaceService:
    """Local workspace lifecycle service used by OSS bootstrap and account flows."""

    def __init__(
        self,
        ap: Application,
        *,
        policy: SingleWorkspacePolicy | CloudWorkspacePolicy | None = None,
        instance_uuid: str | None = None,
    ) -> None:
        self.ap = ap
        self.policy = policy or SingleWorkspacePolicy()
        self._instance_uuid = instance_uuid

    @property
    def instance_uuid(self) -> str:
        instance_uuid = (self._instance_uuid or constants.instance_id).strip()
        if not instance_uuid:
            raise WorkspaceInvariantError('LangBot instance UUID is empty')
        return instance_uuid

    async def get_workspace(
        self,
        workspace_uuid: str,
        *,
        session: AsyncSession | None = None,
    ) -> Workspace:
        """Load one Workspace projected onto this LangBot instance."""

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if session is None and callable(tenant_uow):
            async with tenant_uow(workspace_uuid) as uow:
                return await self.get_workspace(workspace_uuid, session=uow.session)

        async def operation(repository: WorkspaceRepository) -> Workspace:
            workspace = await repository.get_workspace(workspace_uuid)
            if workspace is None or workspace.instance_uuid != self.instance_uuid:
                raise WorkspaceNotFoundError('Workspace not found')
            return workspace

        return await self._run(operation, session=session)

    async def get_singleton_workspace(self, *, session: AsyncSession | None = None) -> Workspace:
        async def operation(repository: WorkspaceRepository) -> Workspace:
            workspaces = await repository.list_local_workspaces(self.instance_uuid)
            if not workspaces:
                raise WorkspaceNotFoundError('The local workspace has not been initialized')
            if len(workspaces) != 1:
                raise WorkspaceInvariantError(
                    f'Expected one local workspace for {self.instance_uuid!r}, found {len(workspaces)}'
                )
            return workspaces[0]

        return await self._run(operation, session=session)

    async def get_execution_state(
        self,
        workspace_uuid: str,
        *,
        session: AsyncSession | None = None,
    ) -> WorkspaceExecutionState:
        """Load a Workspace execution state and validate its instance binding."""

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if session is None and callable(tenant_uow):
            async with tenant_uow(workspace_uuid) as uow:
                return await self.get_execution_state(workspace_uuid, session=uow.session)

        async def operation(repository: WorkspaceRepository) -> WorkspaceExecutionState:
            execution_state = await repository.get_execution_state(workspace_uuid)
            if execution_state is None:
                raise WorkspaceExecutionUnavailableError(f'Workspace {workspace_uuid!r} has no execution state')
            if execution_state.instance_uuid != self.instance_uuid:
                raise WorkspaceInvariantError(
                    f'Workspace {workspace_uuid!r} execution state belongs to another instance'
                )
            return execution_state

        return await self._run(operation, session=session)

    async def list_active_execution_bindings(self) -> list[WorkspaceExecutionBinding]:
        """Discover this instance's active Workspaces, then validate each tenant projection.

        The instance discovery transaction may only reveal active, unfenced
        execution-state identifiers.  It is closed before any Workspace data is
        read; every returned binding is revalidated inside its own tenant unit
        of work.
        """

        instance_discovery_uow = getattr(self.ap.persistence_mgr, 'instance_discovery_uow', None)
        statement = (
            sqlalchemy.select(WorkspaceExecutionState.workspace_uuid)
            .where(
                WorkspaceExecutionState.instance_uuid == self.instance_uuid,
                WorkspaceExecutionState.state == WorkspaceExecutionStatus.ACTIVE.value,
                WorkspaceExecutionState.write_fenced == sqlalchemy.false(),
            )
            .order_by(WorkspaceExecutionState.workspace_uuid)
        )
        if callable(instance_discovery_uow):
            async with instance_discovery_uow(self.instance_uuid) as uow:
                result = await uow.session.execute(statement)
                workspace_uuids = list(result.scalars().all())
        else:
            # Compatibility for lightweight test doubles. Production managers
            # always expose the explicit discovery scope.
            result = await self.ap.persistence_mgr.execute_async(statement)
            workspace_uuids = list(result.scalars().all())

        bindings: list[WorkspaceExecutionBinding] = []
        for workspace_uuid in workspace_uuids:
            try:
                bindings.append(await self.get_execution_binding(workspace_uuid))
            except (
                WorkspaceExecutionUnavailableError,
                WorkspaceInvariantError,
                WorkspaceNotFoundError,
            ) as exc:
                self.ap.logger.warning(f'Skipping invalid Workspace execution projection {workspace_uuid!r}: {exc}')
        return bindings

    async def get_execution_binding(
        self,
        workspace_uuid: str | None = None,
        *,
        expected_generation: int | None = None,
        session: AsyncSession | None = None,
        _require_local: bool = False,
    ) -> WorkspaceExecutionBinding:
        """Resolve an active, unfenced binding projected onto this instance.

        SaaS Workspaces are projected by a closed control plane, but Core still
        validates the local projection and execution fence. Callers never infer
        a Workspace from source or recency.
        """

        self._require_deployment_admission()

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if session is None and workspace_uuid is not None and callable(tenant_uow):
            async with tenant_uow(workspace_uuid) as uow:
                return await self.get_execution_binding(
                    workspace_uuid,
                    expected_generation=expected_generation,
                    session=uow.session,
                    _require_local=_require_local,
                )

        async def operation(repository: WorkspaceRepository) -> WorkspaceExecutionBinding:
            if workspace_uuid is None:
                workspaces = await repository.list_local_workspaces(self.instance_uuid)
                if not workspaces:
                    raise WorkspaceNotFoundError('The local workspace has not been initialized')
                if len(workspaces) != 1:
                    raise WorkspaceInvariantError(
                        f'Expected one local workspace for {self.instance_uuid!r}, found {len(workspaces)}'
                    )
                workspace = workspaces[0]
            else:
                workspace = await repository.get_workspace(workspace_uuid)
                if workspace is None:
                    raise WorkspaceNotFoundError(f'Workspace {workspace_uuid!r} does not exist')

            if workspace.instance_uuid != self.instance_uuid:
                raise WorkspaceInvariantError(f'Workspace {workspace.uuid!r} belongs to another instance')
            if _require_local and workspace.source != WorkspaceSource.LOCAL.value:
                raise WorkspaceInvariantError(f'Workspace {workspace.uuid!r} is not an OSS local workspace')
            if workspace.status != WorkspaceStatus.ACTIVE.value:
                raise WorkspaceExecutionUnavailableError(f'Workspace {workspace.uuid!r} is not active')

            execution_state = await repository.get_execution_state(workspace.uuid)
            if execution_state is None:
                raise WorkspaceExecutionUnavailableError(f'Workspace {workspace.uuid!r} has no execution state')
            if execution_state.instance_uuid != self.instance_uuid:
                raise WorkspaceInvariantError(
                    f'Workspace {workspace.uuid!r} execution state belongs to another instance'
                )
            expected_source = (
                WorkspaceExecutionSource.LOCAL.value
                if workspace.source == WorkspaceSource.LOCAL.value
                else WorkspaceExecutionSource.CLOUD.value
            )
            if execution_state.source != expected_source:
                raise WorkspaceInvariantError(
                    f'Workspace {workspace.uuid!r} execution source does not match its directory source'
                )
            if execution_state.state != WorkspaceExecutionStatus.ACTIVE.value or execution_state.write_fenced:
                raise WorkspaceExecutionUnavailableError(f'Workspace {workspace.uuid!r} execution is unavailable')
            if execution_state.active_generation <= 0:
                raise WorkspaceInvariantError(f'Workspace {workspace.uuid!r} has an invalid execution generation')
            if expected_generation is not None and execution_state.active_generation != expected_generation:
                raise WorkspaceGenerationMismatchError(
                    f'Workspace {workspace.uuid!r} generation {execution_state.active_generation} '
                    f'does not match expected generation {expected_generation}'
                )

            return WorkspaceExecutionBinding(
                instance_uuid=self.instance_uuid,
                workspace_uuid=workspace.uuid,
                placement_generation=execution_state.active_generation,
                write_fenced=execution_state.write_fenced,
                state=execution_state.state,
            )

        binding = await self._run(operation, session=session)
        # The database lookup can cross the Manifest expiry boundary. Never
        # return a binding that is already invalid at a side-effect boundary.
        self._require_deployment_admission()
        return binding

    async def get_local_execution_binding(
        self,
        workspace_uuid: str | None = None,
        *,
        expected_generation: int | None = None,
        session: AsyncSession | None = None,
    ) -> WorkspaceExecutionBinding:
        """Resolve an active binding and require an OSS-local Workspace."""

        return await self.get_execution_binding(
            workspace_uuid,
            expected_generation=expected_generation,
            session=session,
            _require_local=True,
        )

    async def get_local_execution_context(
        self,
        workspace_uuid: str | None = None,
        *,
        expected_generation: int | None = None,
        session: AsyncSession | None = None,
    ) -> WorkspaceExecutionBinding:
        """Compatibility alias for callers introduced during the tenancy rollout."""
        return await self.get_local_execution_binding(
            workspace_uuid,
            expected_generation=expected_generation,
            session=session,
        )

    async def ensure_singleton_workspace(
        self,
        *,
        session: AsyncSession | None = None,
        name: str = 'Default Workspace',
        slug: str = 'default',
    ) -> Workspace:
        """Create or repair the instance's single local workspace and execution state."""

        async def operation(repository: WorkspaceRepository) -> Workspace:
            workspaces = await repository.list_local_workspaces(self.instance_uuid, for_update=True)
            if len(workspaces) > 1:
                raise WorkspaceInvariantError(f'Multiple local workspaces exist for instance {self.instance_uuid!r}')
            if workspaces:
                workspace = workspaces[0]
            else:
                self.policy.require_workspace_creation_allowed(0)
                workspace = self._new_local_workspace(name=name, slug=slug)
                repository.add_workspace(workspace)
                await repository.flush()

            await self._ensure_execution_state(repository, workspace)
            return workspace

        return await self._run(operation, session=session)

    async def create_local_workspace(
        self,
        *,
        name: str,
        slug: str,
        created_by_account_uuid: str | None = None,
        session: AsyncSession | None = None,
    ) -> Workspace:
        """Create the OSS workspace, enforcing the one-workspace edition limit."""

        async def operation(repository: WorkspaceRepository) -> Workspace:
            current_count = await repository.count_local_workspaces(self.instance_uuid)
            self.policy.require_workspace_creation_allowed(current_count)

            workspace = self._new_local_workspace(
                name=name,
                slug=slug,
                created_by_account_uuid=created_by_account_uuid,
            )
            repository.add_workspace(workspace)
            await repository.flush()
            await self._ensure_execution_state(repository, workspace)
            if created_by_account_uuid is not None:
                await self._claim_initial_owner(repository, workspace, created_by_account_uuid)
            return workspace

        return await self._run(operation, session=session)

    async def claim_initial_owner(
        self,
        account_uuid: str,
        *,
        session: AsyncSession | None = None,
    ) -> WorkspaceMembership:
        """Atomically claim an ownerless singleton workspace for the first account."""

        async def operation(repository: WorkspaceRepository) -> WorkspaceMembership:
            workspaces = await repository.list_local_workspaces(self.instance_uuid, for_update=True)
            if not workspaces:
                self.policy.require_workspace_creation_allowed(0)
                workspace = self._new_local_workspace(name='Default Workspace', slug='default')
                repository.add_workspace(workspace)
                await repository.flush()
            elif len(workspaces) == 1:
                workspace = workspaces[0]
            else:
                raise WorkspaceInvariantError(f'Multiple local workspaces exist for instance {self.instance_uuid!r}')
            await self._ensure_execution_state(repository, workspace)
            return await self._claim_initial_owner(repository, workspace, account_uuid)

        return await self._run(operation, session=session)

    async def bootstrap_local_account(
        self,
        account_uuid: str,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[Workspace, WorkspaceMembership]:
        """Bind the first local account to the singleton workspace as owner."""

        async def operation(repository: WorkspaceRepository) -> tuple[Workspace, WorkspaceMembership]:
            workspaces = await repository.list_local_workspaces(self.instance_uuid, for_update=True)
            if not workspaces:
                self.policy.require_workspace_creation_allowed(0)
                workspace = self._new_local_workspace(name='Default Workspace', slug='default')
                repository.add_workspace(workspace)
                await repository.flush()
            elif len(workspaces) == 1:
                workspace = workspaces[0]
            else:
                raise WorkspaceInvariantError(f'Multiple local workspaces exist for instance {self.instance_uuid!r}')

            await self._ensure_execution_state(repository, workspace)
            membership = await self._claim_initial_owner(repository, workspace, account_uuid)
            return workspace, membership

        return await self._run(operation, session=session)

    async def _claim_initial_owner(
        self,
        repository: WorkspaceRepository,
        workspace: Workspace,
        account_uuid: str,
    ) -> WorkspaceMembership:
        active_owner = await repository.get_active_owner(workspace.uuid, for_update=True)
        if active_owner is not None and active_owner.account_uuid != account_uuid:
            raise WorkspaceOwnerAlreadyExistsError(f'Workspace {workspace.uuid!r} already has an owner')
        if active_owner is not None:
            if workspace.created_by_account_uuid is None:
                workspace.created_by_account_uuid = account_uuid
                await repository.flush()
            return active_owner

        membership = await repository.get_membership(workspace.uuid, account_uuid)
        joined_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        if membership is None:
            membership = WorkspaceMembership(
                uuid=str(uuid.uuid4()),
                workspace_uuid=workspace.uuid,
                account_uuid=account_uuid,
                role=MembershipRole.OWNER.value,
                status=MembershipStatus.ACTIVE.value,
                joined_at=joined_at,
                projection_revision=0,
            )
            repository.add_membership(membership)
        else:
            membership.role = MembershipRole.OWNER.value
            membership.status = MembershipStatus.ACTIVE.value
            membership.joined_at = membership.joined_at or joined_at

        if workspace.created_by_account_uuid is None:
            workspace.created_by_account_uuid = account_uuid
        await repository.flush()
        return membership

    async def _ensure_execution_state(
        self,
        repository: WorkspaceRepository,
        workspace: Workspace,
    ) -> WorkspaceExecutionState:
        execution_state = await repository.get_execution_state(workspace.uuid)
        if execution_state is not None:
            if execution_state.instance_uuid != self.instance_uuid:
                raise WorkspaceInvariantError(
                    f'Workspace {workspace.uuid!r} execution state belongs to another instance'
                )
            return execution_state

        execution_state = WorkspaceExecutionState(
            workspace_uuid=workspace.uuid,
            instance_uuid=self.instance_uuid,
            active_generation=1,
            state=WorkspaceExecutionStatus.ACTIVE.value,
            write_fenced=False,
            source=WorkspaceExecutionSource.LOCAL.value,
            desired_state_revision=0,
        )
        repository.add_execution_state(execution_state)
        await repository.flush()
        return execution_state

    def _new_local_workspace(
        self,
        *,
        name: str,
        slug: str,
        created_by_account_uuid: str | None = None,
    ) -> Workspace:
        return Workspace(
            uuid=str(uuid.uuid4()),
            instance_uuid=self.instance_uuid,
            name=name,
            slug=slug,
            type=WorkspaceType.TEAM.value,
            status=WorkspaceStatus.ACTIVE.value,
            created_by_account_uuid=created_by_account_uuid,
            source=WorkspaceSource.LOCAL.value,
            projection_revision=0,
        )

    async def _run(
        self,
        operation: Callable[[WorkspaceRepository], Awaitable[T]],
        *,
        session: AsyncSession | None,
    ) -> T:
        if session is not None:
            return await operation(WorkspaceRepository(session))

        current_session = getattr(self.ap.persistence_mgr, 'current_session', lambda: None)
        active_session = current_session()
        if active_session is not None:
            return await operation(WorkspaceRepository(active_session))
        if getattr(getattr(self.ap.persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime':
            # Do not let service-local session factories silently bypass the
            # request/task scope enforced by PersistenceManager.
            require_current_session = getattr(self.ap.persistence_mgr, 'require_current_session', None)
            if callable(require_current_session):
                require_current_session()
            raise RuntimeError('Cloud Workspace services require an explicit persistence unit of work')

        session_factory = async_sessionmaker(
            self.ap.persistence_mgr.get_db_engine(),
            expire_on_commit=False,
        )
        async with session_factory() as owned_session:
            async with owned_session.begin():
                return await operation(WorkspaceRepository(owned_session))

    def _require_deployment_admission(self) -> None:
        guard = getattr(self.ap, 'deployment_admission', None)
        if guard is not None:
            guard.require_active()
