"""EventLog store for writing and querying event records."""

from __future__ import annotations

import json
import datetime
import typing
import uuid
import time

import sqlalchemy
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...persistence.datetime_utils import as_naive_utc

from ...entity.persistence.event_log import EventLog
from ...entity.persistence.agent_run import AgentRun


UTC = datetime.timezone.utc


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


class EventLogStore:
    """Store for EventLog records.

    Handles writing events to the event log and querying them.
    All methods are async and use the provided database engine.
    """

    engine: AsyncEngine

    # Hard limits
    MAX_INPUT_SUMMARY_LENGTH = 1000

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def _steering_field(self, name: str, column=None):
        column = EventLog.metadata_json if column is None else column
        if self.engine.dialect.name == 'postgresql':
            return sqlalchemy.cast(column, sqlalchemy.JSON)['steering'][name].as_string()
        return sqlalchemy.func.json_extract(column, f'$.steering.{name}')

    async def append_event(
        self,
        event_id: str | None,
        event_type: str,
        source: str,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        conversation_id: str | None = None,
        thread_id: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        actor_name: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        input_summary: str | None = None,
        input_json: dict[str, typing.Any] | None = None,
        raw_ref: str | None = None,
        run_id: str | None = None,
        runner_id: str | None = None,
        event_time: datetime.datetime | None = None,
        metadata: dict[str, typing.Any] | None = None,
        session: AsyncSession | None = None,
    ) -> str:
        """Append an event to the event log.

        Args:
            event_id: Unique event ID (generated if None)
            event_type: Event type
            source: Event source
            bot_id: Bot UUID
            workspace_id: Workspace ID
            conversation_id: Conversation ID
            thread_id: Thread ID
            actor_type: Actor type
            actor_id: Actor ID
            actor_name: Actor display name
            subject_type: Subject type
            subject_id: Subject ID
            input_summary: Brief input summary
            input_json: Full input JSON
            raw_ref: Reference to raw event payload
            run_id: Run ID processing this event
            runner_id: Runner ID processing this event
            event_time: When the event occurred
            metadata: Additional metadata
            session: Optional owning transaction; the caller commits or rolls back

        Returns:
            The event_id
        """
        if event_id is None:
            event_id = str(uuid.uuid4())

        # Truncate input summary if too long
        if input_summary and len(input_summary) > self.MAX_INPUT_SUMMARY_LENGTH:
            input_summary = input_summary[: self.MAX_INPUT_SUMMARY_LENGTH - 3] + '...'

        values = dict(
            event_id=event_id,
            event_type=event_type,
            event_time=as_naive_utc(event_time),
            source=source,
            bot_id=bot_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            subject_type=subject_type,
            subject_id=subject_id,
            input_summary=input_summary,
            input_json=json.dumps(input_json) if input_json else None,
            raw_ref=raw_ref,
            run_id=run_id,
            runner_id=runner_id,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=as_naive_utc(_utc_now()),
        )
        if session is not None:
            await self._append_in_transaction(session, values, input_json)
        else:
            async with self._session_factory() as owned:
                await self._append_in_transaction(owned, values, input_json)
                await owned.commit()
        return event_id

    async def _append_in_transaction(self, session, values, input_json):
        insert = {'postgresql': postgresql.insert, 'sqlite': sqlite.insert}[self.engine.dialect.name]
        result = await session.execute(
            insert(EventLog).values(**values).on_conflict_do_nothing(index_elements=['event_id'])
        )
        if result.rowcount:
            return
        existing = (
            await session.execute(
                sqlalchemy.select(EventLog).where(
                    EventLog.event_id == values['event_id'],
                )
            )
        ).scalar_one_or_none()
        if existing is None or existing.workspace_id != values['workspace_id'] or existing.bot_id != values['bot_id']:
            raise ValueError('An event ID cannot be reused across Workspaces or bots')
        # Only fill missing identities; another subscriber cannot replace a claimed run.
        updates = {
            field: sqlalchemy.func.coalesce(getattr(EventLog, field), values[field])
            for field in ('run_id', 'runner_id', 'conversation_id', 'thread_id', 'actor_id', 'actor_name')
            if values[field] is not None
        }
        if input_json and ('contents' in input_json or 'attachments' in input_json):
            updates.update(input_json=values['input_json'], input_summary=values['input_summary'])
        if updates:
            await session.execute(
                sqlalchemy.update(EventLog)
                .where(
                    EventLog.event_id == values['event_id'],
                    EventLog.workspace_id == values['workspace_id'],
                )
                .values(**updates)
            )

    async def get_event(
        self,
        event_id: str,
    ) -> dict[str, typing.Any] | None:
        """Get a single event by ID.

        Args:
            event_id: Event ID

        Returns:
            Event record as dict, or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(sqlalchemy.select(EventLog).where(EventLog.event_id == event_id))
            row = result.scalars().first()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def list_pending_steering(
        self,
        *,
        conversation_id: str,
        runner_id: str,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        limit: int = 100,
        binding_id: str | None = None,
    ) -> list[dict[str, typing.Any]]:
        """List queued or leased steering source events for recovery.

        Steering delivery is kept in the event log so a run restart can
        reconstruct inputs that were pulled but never acknowledged.
        """
        limit = max(1, min(int(limit), 100))
        async with self._session_factory() as session:
            query = (
                sqlalchemy.select(EventLog)
                .where(
                    EventLog.event_type == 'message.received',
                    EventLog.conversation_id == conversation_id,
                    EventLog.runner_id == runner_id,
                )
                .where(self._steering_field('status').in_(['queued', 'claimed']))
            )
            if bot_id is not None:
                query = query.where(EventLog.bot_id == bot_id)
            if binding_id is not None:
                query = query.where(
                    EventLog.run_id.in_(sqlalchemy.select(AgentRun.run_id).where(AgentRun.binding_id == binding_id))
                )
            if workspace_id is not None:
                query = query.where(EventLog.workspace_id == workspace_id)
            if thread_id is None:
                query = query.where(EventLog.thread_id.is_(None))
            else:
                query = query.where(EventLog.thread_id == thread_id)
            owner = sqlalchemy.func.coalesce(
                self._steering_field('recovery_run_id'), self._steering_field('delivery_run_id'), EventLog.run_id
            )
            live_runs = sqlalchemy.select(AgentRun.run_id).where(
                AgentRun.status == 'running',
                AgentRun.execution_lease_expires_at > datetime.datetime.now(UTC).replace(tzinfo=None),
            )
            query = query.where(sqlalchemy.or_(owner.is_(None), owner.notin_(live_runs)))
            # Older Hosts wrote dropped audits without updating the source row.
            dropped = sqlalchemy.orm.aliased(EventLog)
            query = (
                query.where(
                    ~sqlalchemy.exists().where(
                        dropped.event_type == 'steering.dropped',
                        dropped.conversation_id == EventLog.conversation_id,
                        dropped.runner_id == EventLog.runner_id,
                        self._steering_field('original_event_id', dropped.metadata_json) == EventLog.event_id,
                    )
                )
                .order_by(EventLog.id.asc())
                .limit(limit)
            )
            result = await session.execute(query)
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def reserve_steering_recovery(self, event_id: str, *, run_id: str) -> bool:
        """Atomically assign a pending source event to one replacement run."""
        async with self._session_factory() as session:
            row = (
                await session.execute(sqlalchemy.select(EventLog).where(EventLog.event_id == event_id))
            ).scalar_one_or_none()
            if row is None:
                return False
            original = row.metadata_json
            metadata = json.loads(original) if original else {}
            steering = metadata.get('steering', {})
            if steering.get('status') not in {'queued', 'claimed'}:
                return False
            now = int(time.time())
            owner_id = steering.get('recovery_run_id') or steering.get('delivery_run_id') or row.run_id
            if owner_id and owner_id != run_id:
                live_owner = await session.scalar(
                    sqlalchemy.select(AgentRun.id).where(
                        AgentRun.run_id == owner_id,
                        AgentRun.status == 'running',
                        AgentRun.execution_lease_expires_at > datetime.datetime.now(UTC).replace(tzinfo=None),
                    )
                )
                if live_owner is not None:
                    return False
            if (
                steering.get('recovery_run_id') not in (None, run_id)
                and steering.get('recovery_lease_expires_at', 0) > now
            ):
                return False
            steering.update(recovery_run_id=run_id, recovery_lease_expires_at=now + 30)
            result = await session.execute(
                sqlalchemy.update(EventLog)
                .where(EventLog.event_id == event_id, EventLog.metadata_json == original)
                .values(metadata_json=json.dumps(metadata))
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            return result.rowcount == 1

    async def claim_steering_delivery(
        self, event_id: str, *, run_id: str, delivery_id: str, lease_expires_at: int
    ) -> bool:
        """Fence delivery across replacement runs and Host processes."""
        async with self._session_factory() as session:
            row = (
                await session.execute(sqlalchemy.select(EventLog).where(EventLog.event_id == event_id))
            ).scalar_one_or_none()
            if row is None:
                return False
            original = row.metadata_json
            metadata = json.loads(original) if original else {}
            steering = metadata.get('steering', {})
            if steering.get('status') not in {'queued', 'claimed'}:
                return False
            now = int(time.time())
            if (
                steering.get('recovery_run_id') not in (None, run_id)
                and steering.get('recovery_lease_expires_at', 0) > now
            ):
                return False
            if steering.get('status') == 'claimed' and steering.get('lease_expires_at', 0) > now:
                return steering.get('delivery_id') == delivery_id and steering.get('delivery_run_id') == run_id
            steering.update(
                status='claimed', delivery_id=delivery_id, delivery_run_id=run_id, lease_expires_at=lease_expires_at
            )
            result = await session.execute(
                sqlalchemy.update(EventLog)
                .where(EventLog.event_id == event_id, EventLog.metadata_json == original)
                .values(metadata_json=json.dumps(metadata))
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            return result.rowcount == 1

    async def update_steering_status(
        self,
        event_id: str,
        *,
        status: str,
        delivery_id: str | None = None,
        lease_expires_at: int | None = None,
        expected_delivery_id: str | None = None,
        owner_run_id: str | None = None,
    ) -> bool:
        """Update durable steering delivery state for one source event."""
        async with self._session_factory() as session:
            row = (
                await session.execute(sqlalchemy.select(EventLog).where(EventLog.event_id == event_id))
            ).scalar_one_or_none()
            if row is None:
                return False
            metadata = json.loads(row.metadata_json) if row.metadata_json else {}
            steering = metadata.setdefault('steering', {})
            if owner_run_id is not None:
                if expected_delivery_id:
                    if (
                        steering.get('status') != 'claimed'
                        or steering.get('delivery_id') != expected_delivery_id
                        or steering.get('delivery_run_id') != owner_run_id
                    ):
                        return False
                elif steering.get('recovery_run_id') not in (None, owner_run_id):
                    return False
            original = row.metadata_json
            steering['status'] = status
            if delivery_id is not None:
                steering['delivery_id'] = delivery_id
            if lease_expires_at is not None:
                steering['lease_expires_at'] = lease_expires_at
            steering.pop('recovery_run_id', None)
            steering.pop('recovery_lease_expires_at', None)
            result = await session.execute(
                sqlalchemy.update(EventLog)
                .where(EventLog.event_id == event_id, EventLog.metadata_json == original)
                .values(metadata_json=json.dumps(metadata))
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            return result.rowcount == 1

    async def acknowledge_steering_deliveries(
        self,
        delivery_ids: typing.Iterable[str],
        *,
        run_id: str | None = None,
        conversation_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[str]:
        """Mark durable steering deliveries acknowledged by their IDs."""
        requested = {str(item) for item in delivery_ids if item}
        if not requested:
            return []
        async with self._session_factory() as session:
            query = sqlalchemy.select(EventLog).where(
                EventLog.event_type == 'message.received', self._steering_field('delivery_id').in_(requested)
            )
            if run_id is not None:
                query = query.where(self._steering_field('delivery_run_id') == run_id)
            if conversation_id is not None:
                query = query.where(EventLog.conversation_id == conversation_id)
            if workspace_id is not None:
                query = query.where(EventLog.workspace_id == workspace_id)
            result = await session.execute(query)
            acknowledged = []
            for row in result.scalars().all():
                metadata = json.loads(row.metadata_json) if row.metadata_json else {}
                steering = metadata.get('steering', {})
                if steering.get('status') not in {'claimed', 'acknowledged'}:
                    continue
                original = row.metadata_json
                steering['status'] = 'acknowledged'
                updated = await session.execute(
                    sqlalchemy.update(EventLog)
                    .where(EventLog.event_id == row.event_id, EventLog.metadata_json == original)
                    .values(metadata_json=json.dumps(metadata))
                    .execution_options(synchronize_session=False)
                )
                if updated.rowcount != 1:
                    raise ValueError('Concurrent steering update; retry acknowledgement')
                acknowledged.append(steering['delivery_id'])
            await session.commit()
            return sorted(acknowledged)

    async def page_events(
        self,
        conversation_id: str | None = None,
        event_types: list[str] | None = None,
        before_seq: int | None = None,
        limit: int = 50,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> tuple[list[dict[str, typing.Any]], int | None, bool]:
        """Page through event records.

        Args:
            conversation_id: Filter by conversation ID
            event_types: Filter by event types
            before_seq: Get events before this sequence number
            limit: Maximum items to return (capped at 100)
            bot_id: Optional bot scope filter
            workspace_id: Optional workspace scope filter
            thread_id: Optional thread scope filter
            strict_thread: When true, require thread_id equality including NULL

        Returns:
            Tuple of (items, next_seq, has_more)
        """
        limit = min(limit, 100)  # Hard cap

        async with self._session_factory() as session:
            query = sqlalchemy.select(EventLog)

            if conversation_id is not None:
                query = query.where(EventLog.conversation_id == conversation_id)
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)

            if event_types:
                query = query.where(EventLog.event_type.in_(event_types))

            if before_seq is not None:
                query = query.where(EventLog.id < before_seq)

            query = query.order_by(EventLog.id.desc()).limit(limit + 1)

            result = await session.execute(query)
            rows = result.scalars().all()

            items = [self._row_to_dict(row) for row in rows[:limit]]
            has_more = len(rows) > limit
            next_seq = items[-1]['id'] if items and has_more else None

            return items, next_seq, has_more

    async def get_latest_cursor(
        self,
        conversation_id: str,
    ) -> str | None:
        """Get the latest cursor for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Cursor string (seq number), or None if no events
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(EventLog.id)
                .where(EventLog.conversation_id == conversation_id)
                .order_by(EventLog.id.desc())
                .limit(1)
            )
            row = result.scalars().first()
            if row is None:
                return None
            return str(row)

    async def has_events_before(
        self,
        conversation_id: str,
        seq: int,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> bool:
        """Check if there are events before a sequence number.

        Args:
            conversation_id: Conversation ID
            seq: Sequence number

        Returns:
            True if there are events before
        """
        async with self._session_factory() as session:
            query = (
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(EventLog)
                .where(EventLog.conversation_id == conversation_id, EventLog.id < seq)
            )
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)
            result = await session.execute(query)
            count = result.scalar()
            return count > 0

    def _apply_scope_filters(
        self,
        query: typing.Any,
        bot_id: str | None,
        workspace_id: str | None,
        thread_id: str | None,
        strict_thread: bool,
    ) -> typing.Any:
        if bot_id is not None:
            query = query.where(EventLog.bot_id == bot_id)
        if workspace_id is not None:
            query = query.where(EventLog.workspace_id == workspace_id)
        if strict_thread:
            if thread_id is None:
                query = query.where(EventLog.thread_id.is_(None))
            else:
                query = query.where(EventLog.thread_id == thread_id)
        return query

    async def cleanup_events_older_than(
        self,
        before: datetime.datetime,
    ) -> int:
        """Delete EventLog rows created before the supplied timestamp."""
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.delete(EventLog).where(EventLog.created_at < as_naive_utc(before))
            )
            await session.commit()
            return result.rowcount or 0

    def _row_to_dict(self, row: EventLog) -> dict[str, typing.Any]:
        """Convert an EventLog row to dict."""
        return {
            'id': row.id,
            'event_id': row.event_id,
            'event_type': row.event_type,
            'event_time': _datetime_to_epoch(row.event_time),
            'source': row.source,
            'bot_id': row.bot_id,
            'workspace_id': row.workspace_id,
            'conversation_id': row.conversation_id,
            'thread_id': row.thread_id,
            'actor_type': row.actor_type,
            'actor_id': row.actor_id,
            'actor_name': row.actor_name,
            'subject_type': row.subject_type,
            'subject_id': row.subject_id,
            'input_summary': row.input_summary,
            'input_json': json.loads(row.input_json) if row.input_json else None,
            'raw_ref': row.raw_ref,
            'run_id': row.run_id,
            'runner_id': row.runner_id,
            'created_at': _datetime_to_epoch(row.created_at),
            'metadata': json.loads(row.metadata_json) if row.metadata_json else {},
        }
