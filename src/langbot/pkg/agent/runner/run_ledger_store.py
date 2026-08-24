"""Run ledger store for Host-owned AgentRun and AgentRunEvent records."""

from __future__ import annotations

import datetime
import json
import typing
import uuid

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...entity.persistence.agent_run import AgentRun, AgentRunEvent, AgentRuntime


UTC = datetime.timezone.utc
RUN_STATUSES = {'created', 'queued', 'claimed', 'running', 'completed', 'failed', 'cancelled', 'timeout'}
TERMINAL_STATUSES = {'completed', 'failed', 'cancelled', 'timeout'}


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def _as_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _datetime_to_epoch(value: datetime.datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return int(value.timestamp())


def _epoch_to_datetime(value: typing.Any) -> datetime.datetime | None:
    if value is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(float(value), UTC)
    except (TypeError, ValueError, OSError):
        return None


def _json_dumps(value: typing.Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _json_loads(value: str | None, default: typing.Any) -> typing.Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _validate_run_status(status: str) -> str:
    normalized = str(status)
    if normalized not in RUN_STATUSES:
        raise ValueError(f'Unknown run status: {normalized}')
    return normalized


def _claim_is_active(
    run: AgentRun,
    *,
    runtime_id: str | None,
    claim_token: str,
    now: datetime.datetime,
) -> bool:
    if run.status != 'claimed' or run.claim_token != claim_token:
        return False
    if runtime_id is not None and run.claimed_by_runtime_id != runtime_id:
        return False
    lease_expires_at = _as_utc(run.claim_lease_expires_at)
    return lease_expires_at is not None and lease_expires_at > now


class RunLedgerStore:
    """Store for Host-owned run lifecycle and result event facts."""

    engine: AsyncEngine

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def create_run(
        self,
        *,
        run_id: str,
        event_id: str | None,
        binding_id: str | None,
        runner_id: str,
        conversation_id: str | None = None,
        thread_id: str | None = None,
        workspace_id: str | None = None,
        bot_id: str | None = None,
        agent_id: str | None = None,
        deadline_at: int | float | None = None,
        authorization: dict[str, typing.Any] | None = None,
        metadata: dict[str, typing.Any] | None = None,
        status: str = 'running',
        queue_name: str | None = None,
        priority: int = 0,
        requested_runtime_id: str | None = None,
    ) -> dict[str, typing.Any]:
        """Create a run if it does not already exist."""
        status = _validate_run_status(status)
        now = _utc_now()
        async with self._session_factory() as session:
            existing = await self._get_run_row(session, run_id)
            if existing is not None:
                return self._run_to_dict(existing)

            run = AgentRun(
                run_id=run_id,
                event_id=event_id,
                agent_id=agent_id,
                binding_id=binding_id,
                runner_id=runner_id,
                conversation_id=conversation_id,
                thread_id=thread_id,
                workspace_id=workspace_id,
                bot_id=bot_id,
                status=status,
                queue_name=queue_name,
                priority=priority,
                requested_runtime_id=requested_runtime_id,
                created_at=now,
                started_at=now if status == 'running' else None,
                updated_at=now,
                deadline_at=_epoch_to_datetime(deadline_at),
                authorization_json=_json_dumps(authorization),
                metadata_json=_json_dumps(metadata),
            )
            session.add(run)
            await session.commit()
            return self._run_to_dict(run)

    async def claim_next_run(
        self,
        *,
        runtime_id: str,
        queue_name: str | None = None,
        lease_seconds: int = 60,
        runner_ids: list[str] | None = None,
        conversation_id: str | None = None,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> dict[str, typing.Any] | None:
        """Claim the next queued or expired-leased run for a runtime."""
        now = _utc_now()
        lease_expires_at = now + datetime.timedelta(seconds=max(int(lease_seconds), 1))
        async with self._session_factory() as session:
            query = sqlalchemy.select(AgentRun).where(
                sqlalchemy.or_(
                    AgentRun.status == 'queued',
                    sqlalchemy.and_(
                        AgentRun.status == 'claimed',
                        AgentRun.claim_lease_expires_at.is_not(None),
                        AgentRun.claim_lease_expires_at <= now,
                    ),
                ),
                sqlalchemy.or_(
                    AgentRun.requested_runtime_id.is_(None),
                    AgentRun.requested_runtime_id == runtime_id,
                ),
            )
            if queue_name is not None:
                query = query.where(AgentRun.queue_name == queue_name)
            if runner_ids:
                query = query.where(AgentRun.runner_id.in_(runner_ids))
            if conversation_id is not None:
                query = query.where(AgentRun.conversation_id == conversation_id)
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)

            query = query.order_by(AgentRun.priority.desc(), AgentRun.id.asc()).limit(1).with_for_update(
                skip_locked=True
            )
            result = await session.execute(query)
            run = result.scalars().first()
            if run is None:
                return None

            run.status = 'claimed'
            run.claimed_by_runtime_id = runtime_id
            run.claim_token = uuid.uuid4().hex
            run.claim_lease_expires_at = lease_expires_at
            run.dispatch_attempts = (run.dispatch_attempts or 0) + 1
            run.last_claimed_at = now
            run.updated_at = now
            await session.commit()
            return self._run_to_dict(run, include_claim_token=True)

    async def renew_claim(
        self,
        *,
        run_id: str,
        claim_token: str,
        runtime_id: str | None = None,
        lease_seconds: int = 60,
    ) -> dict[str, typing.Any] | None:
        """Extend a current claim lease if the token still matches."""
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None or not _claim_is_active(run, runtime_id=runtime_id, claim_token=claim_token, now=now):
                return None

            run.claim_lease_expires_at = now + datetime.timedelta(seconds=max(int(lease_seconds), 1))
            run.updated_at = now
            await session.commit()
            return self._run_to_dict(run)

    async def release_claim(
        self,
        *,
        run_id: str,
        claim_token: str,
        runtime_id: str | None = None,
        status: str = 'queued',
        status_reason: str | None = None,
    ) -> dict[str, typing.Any] | None:
        """Release a current claim lease if the token still matches."""
        status = _validate_run_status(status)
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None or not _claim_is_active(run, runtime_id=runtime_id, claim_token=claim_token, now=now):
                return None

            run.status = status
            run.status_reason = status_reason
            run.claimed_by_runtime_id = None
            run.claim_token = None
            run.claim_lease_expires_at = None
            run.updated_at = now
            if status in TERMINAL_STATUSES:
                run.finished_at = run.finished_at or now
            await session.commit()
            return self._run_to_dict(run)

    async def release_expired_claims(
        self,
        *,
        now: datetime.datetime | None = None,
        status: str = 'queued',
        status_reason: str = 'claim lease expired',
        limit: int = 100,
    ) -> list[dict[str, typing.Any]]:
        """Release claimed runs whose claim lease has expired."""
        status = _validate_run_status(status)
        current_time = now or _utc_now()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        limit = min(max(int(limit), 1), 500)

        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentRun)
                .where(
                    AgentRun.status == 'claimed',
                    AgentRun.claim_lease_expires_at.is_not(None),
                    AgentRun.claim_lease_expires_at <= current_time,
                )
                .order_by(AgentRun.claim_lease_expires_at.asc(), AgentRun.id.asc())
                .limit(limit)
            )
            runs = result.scalars().all()
            for run in runs:
                run.status = status
                run.status_reason = status_reason
                run.claimed_by_runtime_id = None
                run.claim_token = None
                run.claim_lease_expires_at = None
                run.updated_at = current_time
                if status in TERMINAL_STATUSES:
                    run.finished_at = run.finished_at or current_time
            await session.commit()
            return [self._run_to_dict(run) for run in runs]

    async def append_event(
        self,
        *,
        run_id: str,
        sequence: int,
        event_type: str,
        data: dict[str, typing.Any] | None = None,
        usage: dict[str, typing.Any] | None = None,
        source: str = 'runner',
        metadata: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any]:
        """Append one run result event.

        If the same run_id + sequence already exists, the existing row is
        returned. This supports retrying append calls idempotently.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentRunEvent).where(
                    AgentRunEvent.run_id == run_id,
                    AgentRunEvent.sequence == sequence,
                )
            )
            existing = result.scalars().first()
            if existing is not None:
                return self._event_to_dict(existing)

            row = AgentRunEvent(
                run_id=run_id,
                sequence=sequence,
                type=event_type,
                data_json=_json_dumps(data or {}),
                usage_json=_json_dumps(usage),
                created_at=_utc_now(),
                source=source,
                metadata_json=_json_dumps(metadata),
            )
            session.add(row)
            await session.commit()
            return self._event_to_dict(row)

    async def append_audit_event(
        self,
        *,
        run_id: str,
        event_type: str,
        data: dict[str, typing.Any] | None = None,
        metadata: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any] | None:
        """Append a Host-authored audit event after the current max sequence."""
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None:
                return None

            result = await session.execute(
                sqlalchemy.select(sqlalchemy.func.max(AgentRunEvent.sequence)).where(
                    AgentRunEvent.run_id == run_id,
                )
            )
            next_sequence = int(result.scalar_one_or_none() or 0) + 1
            row = AgentRunEvent(
                run_id=run_id,
                sequence=next_sequence,
                type=event_type,
                data_json=_json_dumps(data or {}),
                usage_json=None,
                created_at=_utc_now(),
                source='host',
                metadata_json=_json_dumps(metadata or {}),
            )
            session.add(row)
            await session.commit()
            return self._event_to_dict(row)

    async def finalize_run(
        self,
        *,
        run_id: str,
        status: str,
        status_reason: str | None = None,
        usage: dict[str, typing.Any] | None = None,
        cost: dict[str, typing.Any] | None = None,
        metadata: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any] | None:
        """Update a run to a terminal or current status."""
        status = _validate_run_status(status)
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None:
                return None

            if run.status in TERMINAL_STATUSES and run.status != status:
                raise ValueError(f'Cannot transition terminal run {run_id} from {run.status} to {status}')

            run.status = status
            if status_reason is not None:
                run.status_reason = status_reason
            run.updated_at = now
            if status in TERMINAL_STATUSES:
                run.finished_at = run.finished_at or now
                run.claimed_by_runtime_id = None
                run.claim_token = None
                run.claim_lease_expires_at = None
            if usage is not None:
                run.usage_json = _json_dumps(usage)
            if cost is not None:
                run.cost_json = _json_dumps(cost)
            if metadata is not None:
                existing_metadata = _json_loads(run.metadata_json, {})
                if isinstance(existing_metadata, dict):
                    existing_metadata.update(metadata)
                    run.metadata_json = _json_dumps(existing_metadata)
                else:
                    run.metadata_json = _json_dumps(metadata)
            await session.commit()
            return self._run_to_dict(run)

    async def validate_active_claim(
        self,
        *,
        run_id: str,
        runtime_id: str,
        claim_token: str,
    ) -> bool:
        """Return whether a runtime currently owns an unexpired claim lease."""
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None:
                return False
            return _claim_is_active(run, runtime_id=runtime_id, claim_token=claim_token, now=now)

    async def request_cancel(
        self,
        *,
        run_id: str,
        status_reason: str | None = None,
    ) -> dict[str, typing.Any] | None:
        """Record a cancellation request."""
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None:
                return None
            run.cancel_requested_at = now
            run.updated_at = now
            run.status_reason = status_reason or run.status_reason
            await session.commit()
            return self._run_to_dict(run)

    async def get_run(self, run_id: str) -> dict[str, typing.Any] | None:
        """Get one run by run_id."""
        async with self._session_factory() as session:
            row = await self._get_run_row(session, run_id)
            return self._run_to_dict(row) if row is not None else None

    async def register_runtime(
        self,
        *,
        runtime_id: str,
        status: str = 'online',
        display_name: str | None = None,
        endpoint: str | None = None,
        version: str | None = None,
        capabilities: dict[str, typing.Any] | None = None,
        labels: dict[str, typing.Any] | None = None,
        metadata: dict[str, typing.Any] | None = None,
        heartbeat_deadline_seconds: int = 60,
    ) -> dict[str, typing.Any]:
        """Create or update a runtime registry row and record a heartbeat."""
        now = _utc_now()
        async with self._session_factory() as session:
            runtime = await self._get_runtime_row(session, runtime_id)
            if runtime is None:
                runtime = AgentRuntime(runtime_id=runtime_id, created_at=now)
                session.add(runtime)

            runtime.status = status
            runtime.display_name = display_name
            runtime.endpoint = endpoint
            runtime.version = version
            runtime.capabilities_json = _json_dumps(capabilities or {})
            runtime.labels_json = _json_dumps(labels or {})
            runtime.metadata_json = _json_dumps(metadata or {})
            runtime.last_heartbeat_at = now
            runtime.heartbeat_deadline_at = now + datetime.timedelta(seconds=max(int(heartbeat_deadline_seconds), 1))
            runtime.updated_at = now
            await session.commit()
            return self._runtime_to_dict(runtime)

    async def heartbeat_runtime(
        self,
        *,
        runtime_id: str,
        status: str = 'online',
        heartbeat_deadline_seconds: int = 60,
        capabilities: dict[str, typing.Any] | None = None,
        labels: dict[str, typing.Any] | None = None,
        metadata: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any] | None:
        """Refresh a runtime heartbeat."""
        now = _utc_now()
        async with self._session_factory() as session:
            runtime = await self._get_runtime_row(session, runtime_id)
            if runtime is None:
                return None

            runtime.status = status
            runtime.last_heartbeat_at = now
            runtime.heartbeat_deadline_at = now + datetime.timedelta(seconds=max(int(heartbeat_deadline_seconds), 1))
            runtime.updated_at = now
            if capabilities is not None:
                runtime.capabilities_json = _json_dumps(capabilities)
            if labels is not None:
                runtime.labels_json = _json_dumps(labels)
            if metadata is not None:
                existing_metadata = _json_loads(runtime.metadata_json, {})
                if isinstance(existing_metadata, dict):
                    existing_metadata.update(metadata)
                    runtime.metadata_json = _json_dumps(existing_metadata)
                else:
                    runtime.metadata_json = _json_dumps(metadata)
            await session.commit()
            return self._runtime_to_dict(runtime)

    async def get_runtime(self, runtime_id: str) -> dict[str, typing.Any] | None:
        """Get one runtime by runtime_id."""
        async with self._session_factory() as session:
            row = await self._get_runtime_row(session, runtime_id)
            return self._runtime_to_dict(row) if row is not None else None

    async def list_runtimes(
        self,
        *,
        statuses: list[str] | None = None,
        labels: dict[str, str] | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, typing.Any]], int]:
        """List runtime registry rows.

        Args:
            statuses: Filter by status list
            labels: Filter by labels (key-value pairs)
            limit: Maximum number of rows to return

        Returns:
            Tuple of (runtimes, total_count).
        """
        limit = min(max(int(limit), 1), 500)
        async with self._session_factory() as session:
            # Build base query with status filter
            base_query = sqlalchemy.select(AgentRuntime)
            if statuses:
                base_query = base_query.where(AgentRuntime.status.in_(statuses))

            # Get total count (before label filtering)
            if not labels:
                # Simple case - can count directly in DB
                count_query = sqlalchemy.select(sqlalchemy.func.count(AgentRuntime.id))
                if statuses:
                    count_query = count_query.where(AgentRuntime.status.in_(statuses))
                count_result = await session.execute(count_query)
                total_count = count_result.scalar() or 0

                # Get items
                query = base_query.order_by(AgentRuntime.id.asc()).limit(limit)
                result = await session.execute(query)
                runtimes = [self._runtime_to_dict(row) for row in result.scalars().all()]
            else:
                # Need to fetch all and filter by labels in Python
                query = base_query.order_by(AgentRuntime.id.asc())
                result = await session.execute(query)
                all_runtimes = [self._runtime_to_dict(row) for row in result.scalars().all()]

                # Filter by labels
                runtimes = [
                    rt for rt in all_runtimes
                    if all(rt.get('labels', {}).get(k) == v for k, v in labels.items())
                ]
                total_count = len(runtimes)

                # Apply limit after filtering
                runtimes = runtimes[:limit]

            return runtimes, total_count

    async def mark_stale_runtimes(
        self,
        *,
        now: datetime.datetime | None = None,
        stale_status: str = 'stale',
        stale_after_seconds: int | float | None = None,
    ) -> list[dict[str, typing.Any]]:
        """Mark runtimes stale when their heartbeat deadline has passed."""
        current_time = now or _utc_now()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        stale_conditions: list[typing.Any] = [
            sqlalchemy.and_(
                AgentRuntime.heartbeat_deadline_at.is_not(None),
                AgentRuntime.heartbeat_deadline_at < current_time,
            )
        ]
        if stale_after_seconds is not None:
            try:
                stale_after_delta = datetime.timedelta(seconds=max(float(stale_after_seconds), 0))
            except (TypeError, ValueError):
                stale_after_delta = None
            if stale_after_delta is not None:
                stale_conditions.append(
                    sqlalchemy.and_(
                        AgentRuntime.last_heartbeat_at.is_not(None),
                        AgentRuntime.last_heartbeat_at < current_time - stale_after_delta,
                    )
                )
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentRuntime).where(
                    sqlalchemy.or_(*stale_conditions),
                    AgentRuntime.status != stale_status,
                )
            )
            runtimes = result.scalars().all()
            for runtime in runtimes:
                runtime.status = stale_status
                runtime.updated_at = current_time
            await session.commit()
            return [self._runtime_to_dict(runtime) for runtime in runtimes]

    async def list_runs(
        self,
        *,
        conversation_id: str | None = None,
        statuses: list[str] | None = None,
        before_id: int | None = None,
        limit: int = 50,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
        runner_id: str | None = None,
    ) -> tuple[list[dict[str, typing.Any]], int | None, bool, int]:
        """Page runs by scope.

        Returns:
            Tuple of (items, next_cursor, has_more, total_count).
        """
        limit = min(max(int(limit), 1), 100)
        async with self._session_factory() as session:
            # First get total count
            count_query = sqlalchemy.select(sqlalchemy.func.count(AgentRun.id))
            if conversation_id is not None:
                count_query = count_query.where(AgentRun.conversation_id == conversation_id)
            if statuses:
                count_query = count_query.where(AgentRun.status.in_(statuses))
            if runner_id is not None:
                count_query = count_query.where(AgentRun.runner_id == runner_id)
            count_query = self._apply_scope_filters(count_query, bot_id, workspace_id, thread_id, strict_thread)
            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0

            # Then get items
            query = sqlalchemy.select(AgentRun)
            if conversation_id is not None:
                query = query.where(AgentRun.conversation_id == conversation_id)
            if statuses:
                query = query.where(AgentRun.status.in_(statuses))
            if runner_id is not None:
                query = query.where(AgentRun.runner_id == runner_id)
            if before_id is not None:
                query = query.where(AgentRun.id < before_id)
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)
            query = query.order_by(AgentRun.id.desc()).limit(limit + 1)

            result = await session.execute(query)
            rows = result.scalars().all()
            items = [self._run_to_dict(row) for row in rows[:limit]]
            has_more = len(rows) > limit
            next_cursor = items[-1]['id'] if items and has_more else None

            return items, next_cursor, has_more, total_count

    async def page_run_events(
        self,
        *,
        run_id: str,
        before_sequence: int | None = None,
        after_sequence: int | None = None,
        limit: int = 50,
        direction: str = 'forward',
    ) -> tuple[list[dict[str, typing.Any]], int | None, int | None, bool]:
        """Page result events for one run."""
        limit = min(max(int(limit), 1), 100)
        direction = direction if direction in {'forward', 'backward'} else 'forward'
        async with self._session_factory() as session:
            query = sqlalchemy.select(AgentRunEvent).where(AgentRunEvent.run_id == run_id)
            if before_sequence is not None:
                query = query.where(AgentRunEvent.sequence < before_sequence)
            if after_sequence is not None:
                query = query.where(AgentRunEvent.sequence > after_sequence)

            if direction == 'backward':
                query = query.order_by(AgentRunEvent.sequence.desc())
            else:
                query = query.order_by(AgentRunEvent.sequence.asc())
            query = query.limit(limit + 1)

            result = await session.execute(query)
            rows = result.scalars().all()
            items = [self._event_to_dict(row) for row in rows[:limit]]
            has_more = len(rows) > limit

            if direction == 'backward':
                next_cursor = items[-1]['sequence'] if items and has_more else None
                prev_cursor = items[0]['sequence'] if items else None
            else:
                next_cursor = items[-1]['sequence'] if items and has_more else None
                prev_cursor = items[0]['sequence'] if items else None
            return items, next_cursor, prev_cursor, has_more

    async def _get_run_row(
        self,
        session: AsyncSession,
        run_id: str,
    ) -> AgentRun | None:
        result = await session.execute(sqlalchemy.select(AgentRun).where(AgentRun.run_id == run_id))
        return result.scalars().first()

    async def _get_runtime_row(
        self,
        session: AsyncSession,
        runtime_id: str,
    ) -> AgentRuntime | None:
        result = await session.execute(sqlalchemy.select(AgentRuntime).where(AgentRuntime.runtime_id == runtime_id))
        return result.scalars().first()

    def _apply_scope_filters(
        self,
        query: typing.Any,
        bot_id: str | None,
        workspace_id: str | None,
        thread_id: str | None,
        strict_thread: bool,
    ) -> typing.Any:
        if bot_id is not None:
            query = query.where(AgentRun.bot_id == bot_id)
        if workspace_id is not None:
            query = query.where(AgentRun.workspace_id == workspace_id)
        if strict_thread:
            if thread_id is None:
                query = query.where(AgentRun.thread_id.is_(None))
            else:
                query = query.where(AgentRun.thread_id == thread_id)
        return query

    def _run_to_dict(self, row: AgentRun, *, include_claim_token: bool = False) -> dict[str, typing.Any]:
        data = {
            'id': row.id,
            'run_id': row.run_id,
            'event_id': row.event_id,
            'agent_id': row.agent_id,
            'binding_id': row.binding_id,
            'runner_id': row.runner_id,
            'conversation_id': row.conversation_id,
            'thread_id': row.thread_id,
            'workspace_id': row.workspace_id,
            'bot_id': row.bot_id,
            'status': row.status,
            'status_reason': row.status_reason,
            'queue_name': row.queue_name,
            'priority': row.priority,
            'requested_runtime_id': row.requested_runtime_id,
            'claimed_by_runtime_id': row.claimed_by_runtime_id,
            'claim_lease_expires_at': _datetime_to_epoch(row.claim_lease_expires_at),
            'dispatch_attempts': row.dispatch_attempts,
            'last_claimed_at': _datetime_to_epoch(row.last_claimed_at),
            'created_at': _datetime_to_epoch(row.created_at),
            'started_at': _datetime_to_epoch(row.started_at),
            'finished_at': _datetime_to_epoch(row.finished_at),
            'updated_at': _datetime_to_epoch(row.updated_at),
            'deadline_at': _datetime_to_epoch(row.deadline_at),
            'cancel_requested_at': _datetime_to_epoch(row.cancel_requested_at),
            'usage': _json_loads(row.usage_json, None),
            'cost': _json_loads(row.cost_json, None),
            'metadata': _json_loads(row.metadata_json, {}),
        }
        if include_claim_token:
            data['claim_token'] = row.claim_token
        return data

    def _runtime_to_dict(self, row: AgentRuntime) -> dict[str, typing.Any]:
        return {
            'id': row.id,
            'runtime_id': row.runtime_id,
            'status': row.status,
            'display_name': row.display_name,
            'endpoint': row.endpoint,
            'version': row.version,
            'capabilities': _json_loads(row.capabilities_json, {}),
            'labels': _json_loads(row.labels_json, {}),
            'metadata': _json_loads(row.metadata_json, {}),
            'last_heartbeat_at': _datetime_to_epoch(row.last_heartbeat_at),
            'heartbeat_deadline_at': _datetime_to_epoch(row.heartbeat_deadline_at),
            'created_at': _datetime_to_epoch(row.created_at),
            'updated_at': _datetime_to_epoch(row.updated_at),
        }

    def _event_to_dict(self, row: AgentRunEvent) -> dict[str, typing.Any]:
        return {
            'id': row.id,
            'run_id': row.run_id,
            'sequence': row.sequence,
            'type': row.type,
            'data': _json_loads(row.data_json, {}),
            'usage': _json_loads(row.usage_json, None),
            'created_at': _datetime_to_epoch(row.created_at),
            'source': row.source,
            'metadata': _json_loads(row.metadata_json, {}),
        }

    async def get_run_stats(
        self,
        *,
        start_time: int,
        end_time: int,
        runner_id: str | None = None,
    ) -> dict[str, typing.Any]:
        """Get run statistics within a time window.

        Args:
            start_time: Unix timestamp for start of window
            end_time: Unix timestamp for end of window
            runner_id: Optional filter by runner

        Returns:
            Dict with status counts, rates, and duration stats.
        """
        from sqlalchemy import func

        start_dt = _epoch_to_datetime(start_time)
        end_dt = _epoch_to_datetime(end_time)

        async with self._session_factory() as session:
            # Base filter for time window
            base_filter = [
                AgentRun.created_at >= start_dt,
                AgentRun.created_at <= end_dt,
            ]
            if runner_id:
                base_filter.append(AgentRun.runner_id == runner_id)

            # Count by status
            status_query = (
                sqlalchemy.select(
                    AgentRun.status,
                    func.count(AgentRun.id).label('count')
                )
                .where(*base_filter)
                .group_by(AgentRun.status)
            )
            status_result = await session.execute(status_query)
            status_counts = {row.status: row.count for row in status_result}

            total_count = sum(status_counts.values())
            completed_count = status_counts.get('completed', 0)
            failed_count = status_counts.get('failed', 0) + status_counts.get('timeout', 0)

            # Calculate rates
            window_hours = max((end_time - start_time) / 3600, 0.001)
            throughput = total_count / window_hours if total_count > 0 else 0
            success_rate = completed_count / total_count if total_count > 0 else None
            failure_rate = failed_count / total_count if total_count > 0 else None

            # Duration stats for completed runs - compute in Python for DB compatibility
            avg_duration_seconds = None
            avg_queue_wait_seconds = None

            # Fetch completed runs with timing data
            timing_query = (
                sqlalchemy.select(
                    AgentRun.started_at,
                    AgentRun.finished_at,
                    AgentRun.created_at,
                )
                .where(
                    AgentRun.status == 'completed',
                    AgentRun.started_at.is_not(None),
                    AgentRun.finished_at.is_not(None),
                    *base_filter
                )
            )
            timing_result = await session.execute(timing_query)
            timing_rows = timing_result.all()

            if timing_rows:
                durations = []
                for row in timing_rows:
                    if row.finished_at and row.started_at:
                        delta = row.finished_at - row.started_at
                        durations.append(delta.total_seconds())
                if durations:
                    avg_duration_seconds = round(sum(durations) / len(durations), 2)

            # Queue wait time - compute in Python
            queue_query = (
                sqlalchemy.select(
                    AgentRun.created_at,
                    AgentRun.started_at,
                )
                .where(
                    AgentRun.started_at.is_not(None),
                    *base_filter
                )
            )
            queue_result = await session.execute(queue_query)
            queue_rows = queue_result.all()

            if queue_rows:
                waits = []
                for row in queue_rows:
                    if row.started_at and row.created_at:
                        delta = row.started_at - row.created_at
                        wait_seconds = delta.total_seconds()
                        if wait_seconds >= 0:  # Only count positive waits
                            waits.append(wait_seconds)
                if waits:
                    avg_queue_wait_seconds = round(sum(waits) / len(waits), 2)

            return {
                'start_time': start_time,
                'end_time': end_time,
                'total_count': total_count,
                'created_count': status_counts.get('created', 0),
                'queued_count': status_counts.get('queued', 0),
                'claimed_count': status_counts.get('claimed', 0),
                'running_count': status_counts.get('running', 0),
                'completed_count': completed_count,
                'failed_count': status_counts.get('failed', 0),
                'cancelled_count': status_counts.get('cancelled', 0),
                'timeout_count': status_counts.get('timeout', 0),
                'throughput_per_hour': round(throughput, 2),
                'success_rate': round(success_rate, 4) if success_rate is not None else None,
                'failure_rate': round(failure_rate, 4) if failure_rate is not None else None,
                'avg_duration_seconds': avg_duration_seconds,
                'p50_duration_seconds': None,  # Requires more complex calculation
                'p95_duration_seconds': None,
                'p99_duration_seconds': None,
                'avg_queue_wait_seconds': avg_queue_wait_seconds,
            }

    async def get_runtime_stats(self) -> dict[str, typing.Any]:
        """Get runtime registry statistics.

        Returns:
            Dict with counts, heartbeat health, and capacity.
        """
        from sqlalchemy import func

        now = _utc_now()

        async with self._session_factory() as session:
            # Count by status
            status_query = (
                sqlalchemy.select(
                    AgentRuntime.status,
                    func.count(AgentRuntime.id).label('count')
                )
                .group_by(AgentRuntime.status)
            )
            status_result = await session.execute(status_query)
            status_counts = {row.status: row.count for row in status_result}

            total_count = sum(status_counts.values())
            online_count = status_counts.get('online', 0)
            stale_count = status_counts.get('stale', 0)

            # Heartbeat age stats - compute in Python for DB compatibility
            avg_heartbeat_age = None
            max_heartbeat_age = None

            heartbeat_query = (
                sqlalchemy.select(AgentRuntime.last_heartbeat_at)
                .where(AgentRuntime.last_heartbeat_at.is_not(None))
            )
            heartbeat_result = await session.execute(heartbeat_query)
            heartbeat_rows = heartbeat_result.all()

            if heartbeat_rows:
                ages = []
                for row in heartbeat_rows:
                    heartbeat_at = _as_utc(row.last_heartbeat_at)
                    if heartbeat_at:
                        delta = now - heartbeat_at
                        age_seconds = delta.total_seconds()
                        if age_seconds >= 0:
                            ages.append(age_seconds)
                if ages:
                    avg_heartbeat_age = round(sum(ages) / len(ages), 2)
                    max_heartbeat_age = round(max(ages), 2)

            active_runs_query = (
                sqlalchemy.select(func.count(AgentRun.id))
                .where(AgentRun.status.in_(['running', 'claimed']))
            )
            active_runs_result = await session.execute(active_runs_query)
            active_runs = active_runs_result.scalar() or 0
            claimed_runs_query = (
                sqlalchemy.select(func.count(AgentRun.id))
                .where(AgentRun.status == 'claimed')
            )
            claimed_runs_result = await session.execute(claimed_runs_query)
            claimed_runs = claimed_runs_result.scalar() or 0

            return {
                'total_count': total_count,
                'online_count': online_count,
                'stale_count': stale_count,
                'avg_heartbeat_age_seconds': avg_heartbeat_age,
                'max_heartbeat_age_seconds': max_heartbeat_age,
                'active_runs': active_runs,
                'claimed_runs': claimed_runs,
            }

    async def get_runner_stats(
        self,
        *,
        start_time: int,
        end_time: int,
        limit: int = 50,
    ) -> list[dict[str, typing.Any]]:
        """Get runner-aggregated statistics.

        Args:
            start_time: Unix timestamp for start of window
            end_time: Unix timestamp for end of window
            limit: Maximum number of runners to return

        Returns:
            List of dicts with per-runner statistics.
        """
        from sqlalchemy import func

        start_dt = _epoch_to_datetime(start_time)
        end_dt = _epoch_to_datetime(end_time)
        limit = min(max(limit, 1), 100)

        async with self._session_factory() as session:
            # Aggregate runs by runner_id
            query = (
                sqlalchemy.select(
                    AgentRun.runner_id,
                    func.count(AgentRun.id).label('total'),
                    func.sum(
                        sqlalchemy.case(
                            (AgentRun.status.in_(['queued', 'claimed', 'running']), 1),
                            else_=0
                        )
                    ).label('active'),
                    func.sum(
                        sqlalchemy.case(
                            (AgentRun.status == 'completed', 1),
                            else_=0
                        )
                    ).label('completed'),
                    func.sum(
                        sqlalchemy.case(
                            (AgentRun.status.in_(['failed', 'timeout']), 1),
                            else_=0
                        )
                    ).label('failed'),
                )
                .where(
                    AgentRun.created_at >= start_dt,
                    AgentRun.created_at <= end_dt,
                    AgentRun.runner_id.is_not(None),
                )
                .group_by(AgentRun.runner_id)
                .order_by(func.count(AgentRun.id).desc())
                .limit(limit)
            )

            result = await session.execute(query)
            rows = result.all()

            stats = []
            for row in rows:
                runner_id = row.runner_id or 'unknown'
                total = row.total or 0
                completed = row.completed or 0
                failed = row.failed or 0
                success_rate = completed / total if total > 0 else None

                stats.append({
                    'runner_id': runner_id,
                    'runner_label': None,  # Would need to join with runner descriptors
                    'plugin_identity': None,
                    'total_runs': total,
                    'active_runs': row.active or 0,
                    'completed_runs': completed,
                    'failed_runs': failed,
                    'success_rate': round(success_rate, 4) if success_rate is not None else None,
                    'avg_duration_seconds': None,  # Would need more complex query
                })

            return stats
