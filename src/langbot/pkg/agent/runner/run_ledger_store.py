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
TERMINAL_STATUSES = {'completed', 'failed', 'cancelled', 'timeout'}


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(UTC)


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
            return self._run_to_dict(run)

    async def renew_claim(
        self,
        *,
        run_id: str,
        claim_token: str,
        lease_seconds: int = 60,
    ) -> dict[str, typing.Any] | None:
        """Extend a current claim lease if the token still matches."""
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None or run.status != 'claimed' or run.claim_token != claim_token:
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
        status: str = 'queued',
        status_reason: str | None = None,
    ) -> dict[str, typing.Any] | None:
        """Release a current claim lease if the token still matches."""
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None or run.status != 'claimed' or run.claim_token != claim_token:
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
        artifact_refs: list[dict[str, typing.Any]] | None = None,
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
                artifact_refs_json=_json_dumps(artifact_refs or []),
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
                artifact_refs_json=_json_dumps([]),
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
        now = _utc_now()
        async with self._session_factory() as session:
            run = await self._get_run_row(session, run_id)
            if run is None:
                return None

            run.status = status
            run.status_reason = status_reason
            run.updated_at = now
            if status in TERMINAL_STATUSES:
                run.finished_at = run.finished_at or now
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
        limit: int = 100,
    ) -> list[dict[str, typing.Any]]:
        """List runtime registry rows."""
        limit = min(max(int(limit), 1), 500)
        async with self._session_factory() as session:
            query = sqlalchemy.select(AgentRuntime)
            if statuses:
                query = query.where(AgentRuntime.status.in_(statuses))
            query = query.order_by(AgentRuntime.id.asc()).limit(limit)
            result = await session.execute(query)
            return [self._runtime_to_dict(row) for row in result.scalars().all()]

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
    ) -> tuple[list[dict[str, typing.Any]], int | None, bool]:
        """Page runs by scope."""
        limit = min(max(int(limit), 1), 100)
        async with self._session_factory() as session:
            query = sqlalchemy.select(AgentRun)
            if conversation_id is not None:
                query = query.where(AgentRun.conversation_id == conversation_id)
            if statuses:
                query = query.where(AgentRun.status.in_(statuses))
            if before_id is not None:
                query = query.where(AgentRun.id < before_id)
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)
            query = query.order_by(AgentRun.id.desc()).limit(limit + 1)

            result = await session.execute(query)
            rows = result.scalars().all()
            items = [self._run_to_dict(row) for row in rows[:limit]]
            has_more = len(rows) > limit
            next_cursor = items[-1]['id'] if items and has_more else None
            return items, next_cursor, has_more

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

    def _run_to_dict(self, row: AgentRun) -> dict[str, typing.Any]:
        return {
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
            'claim_token': row.claim_token,
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
            'artifact_refs': _json_loads(row.artifact_refs_json, []),
            'metadata': _json_loads(row.metadata_json, {}),
        }
