from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import time
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

import sqlalchemy
from sqlalchemy.dialects import postgresql, sqlite

from ..entity.persistence.cloud_directory import DirectoryProjectionInbox, DirectoryProjectionState
from ..entity.persistence.user import AccountSource, AccountStatus, User
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
)
from .directory import (
    DirectoryDelta,
    DirectoryEvent,
    DirectoryEventBatch,
    DirectoryMember,
    DirectoryProjectionLimits,
    DirectoryProjectionProvider,
    DirectoryProjectionUnavailableError,
    DirectorySnapshot,
    DirectoryWorkspace,
)
from .entitlements import EntitlementResolver


if TYPE_CHECKING:
    from ..core.app import Application


_ROLE_MAP = {
    'owner': MembershipRole.OWNER.value,
    'admin': MembershipRole.ADMIN.value,
    # Space deliberately exposes a smaller product role vocabulary. A regular
    # SaaS member receives the Core developer role; operator/viewer can be
    # introduced later without changing the signed directory contract.
    'member': MembershipRole.DEVELOPER.value,
    'developer': MembershipRole.DEVELOPER.value,
    'operator': MembershipRole.OPERATOR.value,
    'viewer': MembershipRole.VIEWER.value,
}
_ACCOUNT_STATUS_MAP = {
    'active': AccountStatus.ACTIVE.value,
    'blocked': AccountStatus.DISABLED.value,
    'disabled': AccountStatus.DISABLED.value,
    'deleted': AccountStatus.DELETED.value,
}
_MEMBERSHIP_STATUS_MAP = {
    'active': MembershipStatus.ACTIVE.value,
    'invited': MembershipStatus.DISABLED.value,
    'disabled': MembershipStatus.DISABLED.value,
    'removed': MembershipStatus.REMOVED.value,
}
_INCREMENTAL_PROJECTION_FINGERPRINT = hashlib.sha256(b'langbot-directory-incremental-v1').hexdigest()
_ACCOUNT_QUERY_CHUNK_SIZE = 500


class _DirectorySnapshotSuperseded(DirectoryProjectionUnavailableError):
    """A valid snapshot lost a race with a newer shared projection."""


class DirectoryProjectionService:
    """Project a verified SaaS directory into Core-owned tenant tables.

    The closed adapter verifies transport signatures and returns immutable
    models. Core owns database transactions, revision checks, execution fences,
    and readiness. This keeps the ORM and PostgreSQL RLS boundary out of the
    closed control-plane package.
    """

    def __init__(
        self,
        ap: Application,
        provider: DirectoryProjectionProvider,
        instance_uuid: str,
        *,
        sync_interval_seconds: float = 5.0,
        max_staleness_seconds: float = 60.0,
        event_limit: int = 100,
        limits: DirectoryProjectionLimits | None = None,
        monotonic_time: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(provider, DirectoryProjectionProvider):
            raise TypeError('Cloud directory projection requires a DirectoryProjectionProvider')
        if not instance_uuid.strip():
            raise ValueError('Cloud directory projection requires an instance UUID')
        if sync_interval_seconds <= 0:
            raise ValueError('Directory sync interval must be positive')
        if max_staleness_seconds <= sync_interval_seconds:
            raise ValueError('Directory max staleness must exceed the sync interval')
        if event_limit <= 0 or event_limit > 100:
            raise ValueError('Directory event limit must be between 1 and 100')
        if limits is not None and not isinstance(limits, DirectoryProjectionLimits):
            raise TypeError('Directory projection limits must be a DirectoryProjectionLimits value')
        self.ap = ap
        self.provider = provider
        self.instance_uuid = instance_uuid.strip()
        self.sync_interval_seconds = float(sync_interval_seconds)
        self.max_staleness_seconds = float(max_staleness_seconds)
        self.event_limit = event_limit
        self.limits = limits or DirectoryProjectionLimits()
        self._monotonic_time = monotonic_time
        self._last_success_monotonic: float | None = None
        self._ready = False
        self._active_workspace_count = 0
        self._last_batch_workspace_count = 0
        self._last_batch_membership_count = 0
        # Every runtime replica must consume the event stream independently:
        # entitlement snapshots live in the closed adapter's process memory.
        # The database cursor remains the shared projection high-water mark,
        # while this cursor tracks what this process has actually observed.
        self._consumer_cursor: int | None = None

    async def initialize(self) -> None:
        """Block Cloud startup until one full signed snapshot is committed."""

        last_superseded: _DirectorySnapshotSuperseded | None = None
        for _attempt in range(5):
            snapshot = await self.provider.fetch_snapshot(self.instance_uuid)
            try:
                await self.apply_snapshot(snapshot)
            except _DirectorySnapshotSuperseded as exc:
                last_superseded = exc
                continue
            self._consumer_cursor = snapshot.cursor
            return
        raise DirectoryProjectionUnavailableError(
            'Directory snapshot was repeatedly superseded by another runtime replica'
        ) from last_superseded

    async def run(self) -> None:
        """Continuously refresh the directory and fail closed when it goes stale."""

        delay = self.sync_interval_seconds
        while True:
            try:
                await asyncio.sleep(delay)
                await self.sync_once()
                delay = self.sync_interval_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                self.ap.logger.exception('Cloud directory synchronization failed')
                delay = min(max(delay * 2, self.sync_interval_seconds), self.max_staleness_seconds / 2)

    async def sync_once(self) -> None:
        cursor = self._consumer_cursor
        if cursor is None:
            await self.initialize()
            return
        batch = await self.provider.fetch_events(
            self.instance_uuid,
            cursor,
            self.event_limit,
        )
        batch = DirectoryEventBatch.model_validate(batch.model_dump())
        self._validate_batch(batch, expected_after_cursor=cursor)
        if batch.events:
            directory_revisions = self._directory_event_revisions(batch.events)
            if directory_revisions:
                requested_workspace_uuids = tuple(sorted(directory_revisions))
                delta = await self.provider.fetch_workspaces(
                    self.instance_uuid,
                    requested_workspace_uuids,
                )
                await self.apply_delta(delta, batch)
            else:
                await self.apply_event_batch(batch)
            self._consumer_cursor = batch.cursor
            return
        await self._touch_freshness(cursor)

    def require_ready(self) -> None:
        """Fail synchronously at execution admission when projection is stale."""

        last_success = self._last_success_monotonic
        if not self._ready or last_success is None:
            raise DirectoryProjectionUnavailableError('Cloud directory projection is not ready')
        if self._monotonic_time() - last_success >= self.max_staleness_seconds:
            raise DirectoryProjectionUnavailableError('Cloud directory projection is stale')

    def resource_snapshot(self) -> dict[str, int]:
        """Return aggregate, tenant-free cardinality gauges for health checks."""

        return {
            'active_workspaces': self._active_workspace_count,
            'max_active_workspaces': self.limits.max_active_workspaces,
            'last_batch_workspaces': self._last_batch_workspace_count,
            'last_batch_memberships': self._last_batch_membership_count,
            'max_snapshot_workspaces': self.limits.max_snapshot_workspaces,
            'max_snapshot_memberships': self.limits.max_snapshot_memberships,
        }

    def _validate_batch_capacity(
        self,
        workspaces: tuple[DirectoryWorkspace, ...],
        *,
        full_snapshot: bool,
    ) -> tuple[int, int]:
        workspace_count = len(workspaces)
        if full_snapshot and workspace_count > self.limits.max_snapshot_workspaces:
            raise DirectoryProjectionUnavailableError(
                'Directory snapshot Workspace capacity exceeded '
                f'({workspace_count} > {self.limits.max_snapshot_workspaces})'
            )

        active_count = 0
        membership_count = 0
        for workspace in workspaces:
            if workspace.status == WorkspaceStatus.ACTIVE.value:
                active_count += 1
            membership_count += len(workspace.members)
            if membership_count > self.limits.max_snapshot_memberships:
                raise DirectoryProjectionUnavailableError(
                    'Directory membership capacity exceeded '
                    f'({membership_count} > {self.limits.max_snapshot_memberships})'
                )
        if active_count > self.limits.max_active_workspaces:
            raise DirectoryProjectionUnavailableError(
                f'Directory active Workspace capacity exceeded ({active_count} > {self.limits.max_active_workspaces})'
            )
        return workspace_count, membership_count

    async def _enforce_active_workspace_capacity(self, session: Any) -> int:
        """Count the committed candidate state while holding the projection lock.

        Full snapshots can validate their own active count before doing any
        database work. Incremental deltas cannot know the instance total, so
        every projection path also checks the database after applying fences.
        The caller holds the per-instance DirectoryProjectionState row lock;
        concurrent replicas therefore cannot race two individually-admitted
        deltas above the instance ceiling.
        """

        active_count = int(
            (
                await session.scalar(
                    sqlalchemy.select(sqlalchemy.func.count())
                    .select_from(Workspace)
                    .where(
                        Workspace.instance_uuid == self.instance_uuid,
                        Workspace.source == WorkspaceSource.CLOUD_PROJECTION.value,
                        Workspace.status == WorkspaceStatus.ACTIVE.value,
                    )
                )
            )
            or 0
        )
        if active_count > self.limits.max_active_workspaces:
            raise DirectoryProjectionUnavailableError(
                f'Projected active Workspace capacity exceeded ({active_count} > {self.limits.max_active_workspaces})'
            )
        return active_count

    def _record_batch_cardinality(
        self,
        *,
        active_workspaces: int,
        workspaces: int,
        memberships: int,
    ) -> None:
        self._active_workspace_count = active_workspaces
        self._last_batch_workspace_count = workspaces
        self._last_batch_membership_count = memberships

    async def apply_snapshot(
        self,
        snapshot: DirectorySnapshot,
        *,
        events: Iterable[DirectoryEvent] = (),
    ) -> None:
        """Atomically apply one monotonic full snapshot and its event receipts."""

        if not isinstance(snapshot, DirectorySnapshot):
            raise DirectoryProjectionUnavailableError('Directory provider returned an invalid snapshot')
        workspace_count, membership_count = self._validate_batch_capacity(
            snapshot.workspaces,
            full_snapshot=True,
        )
        snapshot = DirectorySnapshot.model_validate(snapshot.model_dump())
        if snapshot.instance_uuid != self.instance_uuid:
            raise DirectoryProjectionUnavailableError('Directory snapshot targets another LangBot instance')
        fingerprint = self._snapshot_fingerprint(snapshot)
        now = self._utcnow()
        lease_expires_at = now + datetime.timedelta(seconds=self.max_staleness_seconds)
        event_list = tuple(DirectoryEvent.model_validate(event.model_dump()) for event in events)

        directory_uow = getattr(self.ap.persistence_mgr, 'directory_projection_uow', None)
        if not callable(directory_uow):
            raise DirectoryProjectionUnavailableError('Directory projection persistence scope is unavailable')

        async with directory_uow(self.instance_uuid) as uow:
            session = uow.session
            state_values = {
                'instance_uuid': self.instance_uuid,
                'cursor': snapshot.cursor,
                'snapshot_coverage_cursor': snapshot.cursor,
                'snapshot_fingerprint': fingerprint,
                'last_applied_at': now,
                'lease_expires_at': lease_expires_at,
            }
            dialect_name = self.ap.persistence_mgr.get_db_engine().dialect.name
            if dialect_name == 'postgresql':
                insert_state = postgresql.insert(DirectoryProjectionState)
            elif dialect_name == 'sqlite':
                insert_state = sqlite.insert(DirectoryProjectionState)
            else:  # pragma: no cover - Cloud supports PostgreSQL; tests use SQLite.
                raise DirectoryProjectionUnavailableError('Directory projection database is unsupported')
            await session.execute(
                insert_state.values(**state_values).on_conflict_do_nothing(
                    index_elements=[DirectoryProjectionState.instance_uuid]
                )
            )
            state = await session.scalar(
                sqlalchemy.select(DirectoryProjectionState)
                .where(DirectoryProjectionState.instance_uuid == self.instance_uuid)
                .with_for_update()
            )
            if state is None:  # pragma: no cover - insert/select are one transaction.
                raise DirectoryProjectionUnavailableError('Directory projection state could not be locked')
            if snapshot.cursor < state.cursor:
                raise _DirectorySnapshotSuperseded('Directory snapshot cursor rolled back')
            if snapshot.cursor == state.cursor and state.snapshot_fingerprint not in {
                fingerprint,
                _INCREMENTAL_PROJECTION_FINGERPRINT,
            }:
                raise DirectoryProjectionUnavailableError('Directory snapshot cursor has conflicting contents')

            await self._record_events(session, event_list, now=now)
            accounts_by_uuid = await self._apply_accounts(session, snapshot)
            await self._apply_workspaces(session, snapshot, accounts_by_uuid=accounts_by_uuid)
            await self._fence_absent_workspaces(session, snapshot)
            active_workspace_count = await self._enforce_active_workspace_capacity(session)

            state.cursor = snapshot.cursor
            state.snapshot_coverage_cursor = snapshot.cursor
            state.snapshot_fingerprint = fingerprint
            state.last_applied_at = now
            state.lease_expires_at = lease_expires_at

            await self._mark_events_applied(session, event_list, now=now)

            await session.flush()

        await self._reconcile_entitlement_snapshot_set(snapshot)
        self._publish_runtime_execution_projection(snapshot.workspaces)
        self._record_batch_cardinality(
            active_workspaces=active_workspace_count,
            workspaces=workspace_count,
            memberships=membership_count,
        )
        self._record_success()
        self._consumer_cursor = snapshot.cursor

    async def apply_delta(self, delta: DirectoryDelta, batch: DirectoryEventBatch) -> None:
        """Apply only Workspaces named by directory events in one signed page."""

        if not isinstance(delta, DirectoryDelta):
            raise DirectoryProjectionUnavailableError('Directory provider returned an invalid delta')
        if not isinstance(batch, DirectoryEventBatch):
            raise DirectoryProjectionUnavailableError('Directory provider returned an invalid event batch')
        workspace_count, membership_count = self._validate_batch_capacity(
            delta.workspaces,
            full_snapshot=False,
        )
        delta = DirectoryDelta.model_validate(delta.model_dump())
        batch = DirectoryEventBatch.model_validate(batch.model_dump())
        self._validate_batch(batch, expected_after_cursor=batch.after_cursor)
        if delta.instance_uuid != self.instance_uuid:
            raise DirectoryProjectionUnavailableError('Directory delta targets another LangBot instance')

        required_revisions = self._directory_event_revisions(batch.events)
        requested = set(delta.requested_workspace_uuids)
        if not required_revisions or requested != set(required_revisions):
            raise DirectoryProjectionUnavailableError('Directory delta does not match its event batch')
        returned = {workspace.uuid: workspace for workspace in delta.workspaces}
        for workspace_uuid, workspace in returned.items():
            if workspace.projection_revision < required_revisions[workspace_uuid]:
                raise DirectoryProjectionUnavailableError(
                    'Directory Workspace delta is older than its signed event notification'
                )

        now = self._utcnow()
        lease_expires_at = now + datetime.timedelta(seconds=self.max_staleness_seconds)
        directory_uow = getattr(self.ap.persistence_mgr, 'directory_projection_uow', None)
        if not callable(directory_uow):
            raise DirectoryProjectionUnavailableError('Directory projection persistence scope is unavailable')

        projection_caught_up = False
        async with directory_uow(self.instance_uuid) as uow:
            session = uow.session
            state = await session.scalar(
                sqlalchemy.select(DirectoryProjectionState)
                .where(DirectoryProjectionState.instance_uuid == self.instance_uuid)
                .with_for_update()
            )
            if state is None:
                raise DirectoryProjectionUnavailableError('Directory projection state disappeared')
            state_cursor = int(state.cursor)
            if state_cursor < batch.after_cursor:
                raise DirectoryProjectionUnavailableError('Directory projection state cursor rolled back')

            # A different runtime replica may already have applied this page.
            # In that case every receipt through the shared cursor must exist;
            # this replica still fetched the delta and refreshed its own
            # entitlement cache before advancing its process-local cursor.
            await self._record_events(
                session,
                batch.events,
                now=now,
                allow_missing_through_cursor=int(state.snapshot_coverage_cursor),
                reject_missing_through_cursor=state_cursor,
            )
            if state_cursor < batch.cursor:
                projected_delta = DirectorySnapshot(
                    instance_uuid=self.instance_uuid,
                    cursor=batch.cursor,
                    generated_at=delta.generated_at,
                    workspaces=delta.workspaces,
                )
                accounts_by_uuid = await self._apply_accounts(session, projected_delta)
                await self._apply_workspaces(
                    session,
                    projected_delta,
                    accounts_by_uuid=accounts_by_uuid,
                )
                await self._fence_workspaces(
                    session,
                    {
                        workspace_uuid: required_revisions[workspace_uuid]
                        for workspace_uuid in requested - set(returned)
                    },
                )
                state.cursor = batch.cursor
                # A per-Workspace delta cannot prove a full-directory
                # fingerprint. Event receipts and entity revisions protect the
                # incremental path; a later full snapshot replaces this marker.
                state.snapshot_fingerprint = _INCREMENTAL_PROJECTION_FINGERPRINT

            active_workspace_count = await self._enforce_active_workspace_capacity(session)
            state.last_applied_at = now
            state.lease_expires_at = lease_expires_at
            await self._mark_events_applied(session, batch.events, now=now)
            await session.flush()
            projection_caught_up = batch.cursor == batch.high_water_cursor and int(state.cursor) == batch.cursor

        await self._update_entitlement_workspace_activity(
            returned.values(),
            requested_workspace_uuids=requested,
        )
        self._publish_runtime_execution_projection(
            returned.values(),
            affected_workspace_uuids=requested,
        )
        self._record_batch_cardinality(
            active_workspaces=active_workspace_count,
            workspaces=workspace_count,
            memberships=membership_count,
        )
        if projection_caught_up:
            self._record_success()
        self._consumer_cursor = batch.cursor

    def _publish_runtime_execution_projection(
        self,
        workspaces: Iterable[DirectoryWorkspace],
        *,
        affected_workspace_uuids: set[str] | None = None,
    ) -> None:
        """Retire stale runtime scopes without per-session database polling.

        The signed directory transaction is already committed when this hook
        runs. Runtime calls still validate the database fence before and after
        side effects; this notification only releases idle resources promptly.
        """

        tool_manager = getattr(self.ap, 'tool_mgr', None)
        mcp_loader = getattr(tool_manager, 'mcp_tool_loader', None)
        reconcile = getattr(mcp_loader, 'reconcile_execution_projection', None)
        if not callable(reconcile):
            return
        active_generations = {
            workspace.uuid: workspace.execution_generation
            for workspace in workspaces
            if workspace.status == WorkspaceStatus.ACTIVE.value
        }
        try:
            reconcile(
                self.instance_uuid,
                active_generations,
                affected_workspace_uuids=affected_workspace_uuids,
            )
        except Exception:
            # Runtime retirement is a resource cleanup path, not an execution
            # admission boundary. Database-backed call-time fences remain
            # authoritative if a local runtime hook fails.
            self.ap.logger.exception('Failed to publish the Cloud execution projection to MCP runtimes')

    async def _reconcile_entitlement_snapshot_set(
        self,
        snapshot: DirectorySnapshot,
    ) -> None:
        resolver = getattr(self.ap, 'entitlement_resolver', None)
        if not isinstance(resolver, EntitlementResolver):
            return
        await resolver.reconcile_active_workspaces(
            {workspace.uuid for workspace in snapshot.workspaces if workspace.status == WorkspaceStatus.ACTIVE.value}
        )

    async def _update_entitlement_workspace_activity(
        self,
        workspaces: Iterable[DirectoryWorkspace],
        *,
        requested_workspace_uuids: set[str],
    ) -> None:
        resolver = getattr(self.ap, 'entitlement_resolver', None)
        if not isinstance(resolver, EntitlementResolver):
            return
        returned = {workspace.uuid: workspace for workspace in workspaces}
        active = {
            workspace_uuid
            for workspace_uuid, workspace in returned.items()
            if workspace.status == WorkspaceStatus.ACTIVE.value
        }
        await resolver.update_workspace_activity(
            active_workspace_uuids=active,
            inactive_workspace_uuids=requested_workspace_uuids - active,
        )

    async def apply_event_batch(self, batch: DirectoryEventBatch) -> None:
        """Advance non-directory events after the adapter refreshes local caches."""

        if not isinstance(batch, DirectoryEventBatch):
            raise DirectoryProjectionUnavailableError('Directory provider returned an invalid event batch')
        batch = DirectoryEventBatch.model_validate(batch.model_dump())
        self._validate_batch(batch, expected_after_cursor=batch.after_cursor)
        if any(event.event_type == 'directory.changed' for event in batch.events):
            raise DirectoryProjectionUnavailableError('Directory changes require an authoritative full snapshot')

        now = self._utcnow()
        lease_expires_at = now + datetime.timedelta(seconds=self.max_staleness_seconds)
        directory_uow = getattr(self.ap.persistence_mgr, 'directory_projection_uow', None)
        if not callable(directory_uow):
            raise DirectoryProjectionUnavailableError('Directory projection persistence scope is unavailable')
        projection_caught_up = False
        async with directory_uow(self.instance_uuid) as uow:
            state = await uow.session.scalar(
                sqlalchemy.select(DirectoryProjectionState)
                .where(DirectoryProjectionState.instance_uuid == self.instance_uuid)
                .with_for_update()
            )
            if state is None:
                raise DirectoryProjectionUnavailableError('Directory projection state disappeared')
            if state.cursor < batch.after_cursor:
                raise DirectoryProjectionUnavailableError('Directory projection state cursor rolled back')
            await self._record_events(
                uow.session,
                batch.events,
                now=now,
                allow_missing_through_cursor=int(state.snapshot_coverage_cursor),
                reject_missing_through_cursor=int(state.cursor),
            )
            state.cursor = max(int(state.cursor), batch.cursor)
            state.last_applied_at = now
            state.lease_expires_at = lease_expires_at
            await self._mark_events_applied(uow.session, batch.events, now=now)
            await uow.session.flush()
            projection_caught_up = batch.cursor == batch.high_water_cursor and int(state.cursor) == batch.cursor
        if projection_caught_up:
            self._record_success()
        self._consumer_cursor = batch.cursor

    async def _touch_freshness(self, requested_cursor: int) -> None:
        now = self._utcnow()
        lease_expires_at = now + datetime.timedelta(seconds=self.max_staleness_seconds)
        directory_uow = getattr(self.ap.persistence_mgr, 'directory_projection_uow', None)
        if not callable(directory_uow):
            raise DirectoryProjectionUnavailableError('Directory projection persistence scope is unavailable')
        async with directory_uow(self.instance_uuid) as uow:
            state = await uow.session.scalar(
                sqlalchemy.select(DirectoryProjectionState)
                .where(DirectoryProjectionState.instance_uuid == self.instance_uuid)
                .with_for_update()
            )
            if state is None:
                raise DirectoryProjectionUnavailableError('Directory projection state disappeared')
            if state.cursor < requested_cursor:
                raise DirectoryProjectionUnavailableError('Directory projection state cursor rolled back')
            if state.cursor > requested_cursor:
                raise DirectoryProjectionUnavailableError(
                    'This runtime replica has not consumed the shared directory high-water mark'
                )
            state.last_applied_at = now
            state.lease_expires_at = lease_expires_at
            await uow.session.flush()
        self._record_success()

    def _validate_batch(self, batch: DirectoryEventBatch, *, expected_after_cursor: int) -> None:
        if batch.instance_uuid != self.instance_uuid:
            raise DirectoryProjectionUnavailableError('Directory event batch targets another LangBot instance')
        if batch.after_cursor != expected_after_cursor:
            raise DirectoryProjectionUnavailableError('Directory event batch does not match the requested cursor')
        supported_event_types = {'directory.changed', 'entitlement.changed'}
        if any(event.event_type not in supported_event_types for event in batch.events):
            raise DirectoryProjectionUnavailableError('Directory event batch contains an unsupported event type')
        for event in batch.events:
            if event.payload.get('workspace_uuid') != event.aggregate_uuid:
                raise DirectoryProjectionUnavailableError('Directory event payload has a conflicting Workspace scope')
            revision_key = 'directory_revision' if event.event_type == 'directory.changed' else 'entitlement_revision'
            payload_revision = event.payload.get(revision_key)
            if type(payload_revision) is not int or payload_revision != event.revision:
                raise DirectoryProjectionUnavailableError('Directory event payload has a conflicting revision')

    @staticmethod
    def _directory_event_revisions(events: Iterable[DirectoryEvent]) -> dict[str, int]:
        revisions: dict[str, int] = {}
        for event in events:
            if event.event_type == 'directory.changed':
                revisions[event.aggregate_uuid] = max(revisions.get(event.aggregate_uuid, 0), event.revision)
        return revisions

    async def _record_events(
        self,
        session: Any,
        events: tuple[DirectoryEvent, ...],
        *,
        now: datetime.datetime,
        allow_missing_through_cursor: int = -1,
        reject_missing_through_cursor: int | None = None,
    ) -> None:
        for event in events:
            fingerprint = self._fingerprint(event.model_dump(mode='json'))
            existing = await session.scalar(
                sqlalchemy.select(DirectoryProjectionInbox).where(
                    DirectoryProjectionInbox.instance_uuid == self.instance_uuid,
                    DirectoryProjectionInbox.event_uuid == event.uuid,
                )
            )
            if existing is not None:
                if existing.cursor != event.cursor or existing.fingerprint != fingerprint:
                    raise DirectoryProjectionUnavailableError('Directory event UUID has conflicting contents')
                continue
            if (
                reject_missing_through_cursor is not None
                and allow_missing_through_cursor < event.cursor <= reject_missing_through_cursor
            ):
                raise DirectoryProjectionUnavailableError(
                    'Directory projection cursor advanced without a matching event receipt'
                )
            session.add(
                DirectoryProjectionInbox(
                    instance_uuid=self.instance_uuid,
                    event_uuid=event.uuid,
                    cursor=event.cursor,
                    event_type=event.event_type,
                    revision=event.revision,
                    fingerprint=fingerprint,
                    received_at=now,
                    applied_at=None,
                )
            )

    async def _mark_events_applied(
        self,
        session: Any,
        events: Iterable[DirectoryEvent],
        *,
        now: datetime.datetime,
    ) -> None:
        event_uuids = [event.uuid for event in events]
        if not event_uuids:
            return
        inbox_rows = (
            await session.scalars(
                sqlalchemy.select(DirectoryProjectionInbox).where(
                    DirectoryProjectionInbox.instance_uuid == self.instance_uuid,
                    DirectoryProjectionInbox.event_uuid.in_(event_uuids),
                )
            )
        ).all()
        if len(inbox_rows) != len(event_uuids):
            raise DirectoryProjectionUnavailableError('Directory event receipt could not be persisted')
        for row in inbox_rows:
            row.applied_at = now

    async def _apply_accounts(self, session: Any, snapshot: DirectorySnapshot) -> dict[str, User]:
        selected: dict[str, DirectoryMember] = {}
        emails: dict[str, str] = {}
        for workspace in snapshot.workspaces:
            for member in workspace.members:
                email_owner = emails.setdefault(member.normalized_email, member.account_uuid)
                if email_owner != member.account_uuid:
                    raise DirectoryProjectionUnavailableError(
                        'Directory snapshot maps one normalized email to multiple accounts'
                    )
                previous = selected.get(member.account_uuid)
                if previous is not None and self._account_projection(previous) != self._account_projection(member):
                    raise DirectoryProjectionUnavailableError('Directory snapshot has conflicting account projections')
                if previous is None:
                    selected[member.account_uuid] = member

        # Fetch existing UUID and email owners in bounded batches. The previous
        # two SELECTs per unique account made a large but valid directory
        # snapshot produce tens of thousands of serial round trips during
        # startup. The configured membership ceiling bounds the materialized
        # maps, while batching stays below PostgreSQL parameter limits.
        accounts_by_uuid: dict[str, User] = {}
        accounts_by_email: dict[str, User] = {}
        selected_items = list(selected.items())
        for start in range(0, len(selected_items), _ACCOUNT_QUERY_CHUNK_SIZE):
            chunk = selected_items[start : start + _ACCOUNT_QUERY_CHUNK_SIZE]
            account_uuids = [account_uuid for account_uuid, _member in chunk]
            normalized_emails = [member.normalized_email for _account_uuid, member in chunk]
            rows = (
                await session.scalars(
                    sqlalchemy.select(User).where(
                        sqlalchemy.or_(
                            User.uuid.in_(account_uuids),
                            User.normalized_email.in_(normalized_emails),
                        )
                    )
                )
            ).all()
            for account in rows:
                accounts_by_uuid[account.uuid] = account
                accounts_by_email[account.normalized_email] = account

        for account_uuid, member in selected.items():
            account = accounts_by_uuid.get(account_uuid)
            email_account = accounts_by_email.get(member.normalized_email)
            if email_account is not None and email_account.uuid != account_uuid:
                raise DirectoryProjectionUnavailableError('Directory account email collides with another Core account')
            if account is None:
                account = User(
                    uuid=account_uuid,
                    user=member.display_name,
                    normalized_email=member.normalized_email,
                    password='',
                    status=_ACCOUNT_STATUS_MAP[member.account_status],
                    source=AccountSource.CLOUD_PROJECTION.value,
                    projection_revision=snapshot.cursor,
                    account_type='space',
                    space_account_uuid=account_uuid,
                )
                session.add(account)
                accounts_by_uuid[account_uuid] = account
                accounts_by_email[member.normalized_email] = account
                continue
            if account.source != AccountSource.CLOUD_PROJECTION.value:
                raise DirectoryProjectionUnavailableError('Directory account UUID collides with a local Core account')
            if account.projection_revision > snapshot.cursor:
                raise DirectoryProjectionUnavailableError('Directory account revision rolled back')
            projected_account = self._account_projection(member)
            persisted_account = self._persisted_account_projection(account)
            if account.projection_revision == snapshot.cursor and persisted_account != projected_account:
                raise DirectoryProjectionUnavailableError('Directory account revision has conflicting contents')
            if persisted_account == projected_account:
                # A Workspace rename, role update, or another member's change
                # must not revoke this Account's JWT. Account revisions advance
                # only when the Account projection itself changes.
                continue
            account.user = member.display_name
            account.normalized_email = member.normalized_email
            account.status = _ACCOUNT_STATUS_MAP[member.account_status]
            account.projection_revision = snapshot.cursor
            account.account_type = 'space'
            account.space_account_uuid = account_uuid
        await session.flush()
        return accounts_by_uuid

    async def _apply_workspaces(
        self,
        session: Any,
        snapshot: DirectorySnapshot,
        *,
        accounts_by_uuid: dict[str, User],
    ) -> None:
        for candidate in snapshot.workspaces:
            workspace = await session.get(Workspace, candidate.uuid)
            if workspace is None:
                workspace = Workspace(
                    uuid=candidate.uuid,
                    instance_uuid=self.instance_uuid,
                    name=candidate.name,
                    slug=candidate.slug,
                    type=candidate.type,
                    status=candidate.status,
                    created_by_account_uuid=self._projected_creator_uuid(candidate, accounts_by_uuid),
                    source=WorkspaceSource.CLOUD_PROJECTION.value,
                    projection_revision=candidate.projection_revision,
                )
                session.add(workspace)
                await session.flush()
            else:
                self._validate_existing_workspace(workspace, candidate)
                workspace.name = candidate.name
                workspace.slug = candidate.slug
                workspace.type = candidate.type
                workspace.status = candidate.status
                workspace.created_by_account_uuid = self._projected_creator_uuid(candidate, accounts_by_uuid)
                workspace.projection_revision = candidate.projection_revision

            await self._apply_memberships(session, workspace, candidate)
            await self._apply_execution_state(session, workspace, candidate)

    @staticmethod
    def _projected_creator_uuid(
        candidate: DirectoryWorkspace,
        accounts_by_uuid: dict[str, User],
    ) -> str | None:
        creator = accounts_by_uuid.get(candidate.created_by_account_uuid)
        if creator is None:
            if candidate.status == WorkspaceStatus.ACTIVE.value:
                raise DirectoryProjectionUnavailableError('Active Directory Workspace creator is not projected')
            return None
        return candidate.created_by_account_uuid

    def _validate_existing_workspace(self, workspace: Workspace, candidate: DirectoryWorkspace) -> None:
        if workspace.instance_uuid != self.instance_uuid:
            raise DirectoryProjectionUnavailableError('Directory Workspace belongs to another LangBot instance')
        if workspace.source != WorkspaceSource.CLOUD_PROJECTION.value:
            raise DirectoryProjectionUnavailableError('Directory Workspace UUID collides with a local Workspace')
        if workspace.projection_revision > candidate.projection_revision:
            raise DirectoryProjectionUnavailableError('Directory Workspace revision rolled back')
        if workspace.projection_revision == candidate.projection_revision and self._workspace_projection(
            workspace
        ) != self._candidate_workspace_projection(candidate):
            raise DirectoryProjectionUnavailableError('Directory Workspace revision has conflicting contents')

    async def _apply_memberships(
        self,
        session: Any,
        workspace: Workspace,
        candidate: DirectoryWorkspace,
    ) -> None:
        existing = {
            membership.account_uuid: membership
            for membership in (
                await session.scalars(
                    sqlalchemy.select(WorkspaceMembership).where(WorkspaceMembership.workspace_uuid == workspace.uuid)
                )
            ).all()
        }
        included_accounts: set[str] = set()
        for member in candidate.members:
            included_accounts.add(member.account_uuid)
            membership = existing.get(member.account_uuid)
            joined_at = self._naive_utc(member.joined_at)
            role = _ROLE_MAP[member.role]
            status = _MEMBERSHIP_STATUS_MAP[member.membership_status]
            if candidate.status != WorkspaceStatus.ACTIVE.value:
                status = (
                    MembershipStatus.REMOVED.value
                    if candidate.status in {WorkspaceStatus.ARCHIVED.value, WorkspaceStatus.DELETED.value}
                    else MembershipStatus.DISABLED.value
                )
            if membership is None:
                session.add(
                    WorkspaceMembership(
                        uuid=member.membership_uuid,
                        workspace_uuid=workspace.uuid,
                        account_uuid=member.account_uuid,
                        role=role,
                        status=status,
                        joined_at=joined_at,
                        projection_revision=member.projection_revision,
                    )
                )
                continue
            if membership.projection_revision == 0:
                # Revision zero is Core-owned collaboration state. Directory
                # projection seeds memberships, but must not overwrite later
                # invitation, role, or removal decisions made by Core.
                continue
            if membership.uuid != member.membership_uuid:
                raise DirectoryProjectionUnavailableError('Directory membership UUID changed for one account')
            if membership.projection_revision > member.projection_revision:
                raise DirectoryProjectionUnavailableError('Directory membership revision rolled back')
            if membership.projection_revision == member.projection_revision and self._membership_projection(
                membership
            ) != (role, status, self._datetime_fingerprint(joined_at)):
                raise DirectoryProjectionUnavailableError('Directory membership revision has conflicting contents')
            membership.role = role
            membership.status = status
            membership.joined_at = joined_at
            membership.projection_revision = member.projection_revision

        for account_uuid, membership in existing.items():
            if account_uuid not in included_accounts and membership.projection_revision != 0:
                membership.status = MembershipStatus.REMOVED.value
                membership.projection_revision = max(
                    int(membership.projection_revision),
                    candidate.projection_revision,
                )
        await session.flush()

    async def _apply_execution_state(
        self,
        session: Any,
        workspace: Workspace,
        candidate: DirectoryWorkspace,
    ) -> None:
        active = candidate.status == WorkspaceStatus.ACTIVE.value
        desired_state = WorkspaceExecutionStatus.ACTIVE.value if active else WorkspaceExecutionStatus.INACTIVE.value
        execution = await session.get(WorkspaceExecutionState, workspace.uuid)
        if execution is None:
            session.add(
                WorkspaceExecutionState(
                    workspace_uuid=workspace.uuid,
                    instance_uuid=self.instance_uuid,
                    active_generation=candidate.execution_generation,
                    state=desired_state,
                    write_fenced=not active,
                    source=WorkspaceExecutionSource.CLOUD.value,
                    desired_state_revision=candidate.projection_revision,
                )
            )
            await session.flush()
            return
        if execution.instance_uuid != self.instance_uuid or execution.source != WorkspaceExecutionSource.CLOUD.value:
            raise DirectoryProjectionUnavailableError('Directory execution state has an invalid owner')
        if execution.active_generation > candidate.execution_generation:
            raise DirectoryProjectionUnavailableError('Directory execution generation rolled back')
        if execution.desired_state_revision > candidate.projection_revision:
            raise DirectoryProjectionUnavailableError('Directory desired-state revision rolled back')
        if execution.desired_state_revision == candidate.projection_revision and (
            execution.active_generation != candidate.execution_generation
            or execution.state != desired_state
            or execution.write_fenced != (not active)
        ):
            raise DirectoryProjectionUnavailableError(
                'Directory execution state has conflicting contents at one revision'
            )
        execution.active_generation = candidate.execution_generation
        execution.state = desired_state
        execution.write_fenced = not active
        execution.desired_state_revision = candidate.projection_revision
        await session.flush()

    async def _fence_absent_workspaces(self, session: Any, snapshot: DirectorySnapshot) -> None:
        included = {workspace.uuid for workspace in snapshot.workspaces}
        projected = (
            await session.scalars(
                sqlalchemy.select(Workspace)
                .outerjoin(
                    WorkspaceExecutionState,
                    WorkspaceExecutionState.workspace_uuid == Workspace.uuid,
                )
                .where(
                    Workspace.instance_uuid == self.instance_uuid,
                    Workspace.source == WorkspaceSource.CLOUD_PROJECTION.value,
                    sqlalchemy.or_(
                        Workspace.status.not_in(
                            (
                                WorkspaceStatus.ARCHIVED.value,
                                WorkspaceStatus.DELETED.value,
                            )
                        ),
                        WorkspaceExecutionState.state == WorkspaceExecutionStatus.ACTIVE.value,
                        WorkspaceExecutionState.write_fenced == sqlalchemy.false(),
                    ),
                )
            )
        ).all()
        for workspace in projected:
            if workspace.uuid in included:
                continue
            workspace.status = WorkspaceStatus.ARCHIVED.value
            await self._remove_workspace_memberships(session, workspace.uuid)
            execution = await session.get(WorkspaceExecutionState, workspace.uuid)
            if execution is not None:
                execution.state = WorkspaceExecutionStatus.INACTIVE.value
                execution.write_fenced = True
        await session.flush()

    async def _fence_workspaces(self, session: Any, workspace_revisions: dict[str, int]) -> None:
        """Fence requested Workspaces omitted from an authoritative delta."""

        if not workspace_revisions:
            return
        projected = (
            await session.scalars(
                sqlalchemy.select(Workspace).where(
                    Workspace.instance_uuid == self.instance_uuid,
                    Workspace.source == WorkspaceSource.CLOUD_PROJECTION.value,
                    Workspace.uuid.in_(workspace_revisions),
                )
            )
        ).all()
        for workspace in projected:
            tombstone_revision = workspace_revisions[workspace.uuid]
            if int(workspace.projection_revision) > tombstone_revision:
                raise DirectoryProjectionUnavailableError('Directory Workspace tombstone revision rolled back')
            memberships = (
                await session.scalars(
                    sqlalchemy.select(WorkspaceMembership).where(WorkspaceMembership.workspace_uuid == workspace.uuid)
                )
            ).all()
            if any(int(membership.projection_revision) > tombstone_revision for membership in memberships):
                raise DirectoryProjectionUnavailableError('Directory membership tombstone revision rolled back')
            execution = await session.get(WorkspaceExecutionState, workspace.uuid)
            if execution is not None and int(execution.desired_state_revision) > tombstone_revision:
                raise DirectoryProjectionUnavailableError('Directory execution tombstone revision rolled back')
            workspace.status = WorkspaceStatus.ARCHIVED.value
            workspace.projection_revision = max(int(workspace.projection_revision), tombstone_revision)
            await self._remove_workspace_memberships(
                session,
                workspace.uuid,
                projection_revision=tombstone_revision,
                memberships=memberships,
            )
            if execution is not None:
                execution.state = WorkspaceExecutionStatus.INACTIVE.value
                execution.write_fenced = True
                execution.desired_state_revision = max(
                    int(execution.desired_state_revision),
                    tombstone_revision,
                )
        await session.flush()

    async def _remove_workspace_memberships(
        self,
        session: Any,
        workspace_uuid: str,
        *,
        projection_revision: int | None = None,
        memberships: Iterable[WorkspaceMembership] | None = None,
    ) -> None:
        if memberships is None:
            memberships = (
                await session.scalars(
                    sqlalchemy.select(WorkspaceMembership).where(WorkspaceMembership.workspace_uuid == workspace_uuid)
                )
            ).all()
        for membership in memberships:
            membership.status = MembershipStatus.REMOVED.value
            if projection_revision is not None:
                membership.projection_revision = max(
                    int(membership.projection_revision),
                    projection_revision,
                )

    def _record_success(self) -> None:
        self._last_success_monotonic = self._monotonic_time()
        self._ready = True

    @classmethod
    def _snapshot_fingerprint(cls, snapshot: DirectorySnapshot) -> str:
        workspaces = []
        for workspace in sorted(snapshot.workspaces, key=lambda item: item.uuid):
            data = workspace.model_dump(mode='json')
            data['members'] = sorted(data['members'], key=lambda item: item['membership_uuid'])
            workspaces.append(data)
        return cls._fingerprint(
            {
                'instance_uuid': snapshot.instance_uuid,
                'workspaces': workspaces,
            }
        )

    @staticmethod
    def _fingerprint(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _account_projection(member: DirectoryMember) -> tuple[str, str, str]:
        return member.normalized_email, member.display_name, _ACCOUNT_STATUS_MAP[member.account_status]

    @staticmethod
    def _persisted_account_projection(account: User) -> tuple[str, str, str]:
        return account.normalized_email, account.user, account.status

    @staticmethod
    def _workspace_projection(workspace: Workspace) -> tuple[Any, ...]:
        return (
            workspace.name,
            workspace.slug,
            workspace.type,
            workspace.status,
            workspace.created_by_account_uuid,
        )

    @staticmethod
    def _candidate_workspace_projection(candidate: DirectoryWorkspace) -> tuple[Any, ...]:
        return (
            candidate.name,
            candidate.slug,
            candidate.type,
            candidate.status,
            candidate.created_by_account_uuid,
        )

    @classmethod
    def _membership_projection(cls, membership: WorkspaceMembership) -> tuple[Any, ...]:
        return (
            membership.role,
            membership.status,
            cls._datetime_fingerprint(membership.joined_at),
        )

    @staticmethod
    def _datetime_fingerprint(value: datetime.datetime | None) -> str | None:
        if value is None:
            return None
        return DirectoryProjectionService._naive_utc(value).isoformat(timespec='microseconds')

    @staticmethod
    def _naive_utc(value: datetime.datetime | None) -> datetime.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(datetime.UTC).replace(tzinfo=None)

    @staticmethod
    def _utcnow() -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC)
