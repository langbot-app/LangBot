"""EventLog store for writing and querying event records."""
from __future__ import annotations

import json
import datetime
import typing
import uuid

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...entity.persistence.event_log import EventLog


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
        self._session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

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

        Returns:
            The event_id
        """
        if event_id is None:
            event_id = str(uuid.uuid4())

        # Truncate input summary if too long
        if input_summary and len(input_summary) > self.MAX_INPUT_SUMMARY_LENGTH:
            input_summary = input_summary[:self.MAX_INPUT_SUMMARY_LENGTH - 3] + "..."

        async with self._session_factory() as session:
            event = EventLog(
                event_id=event_id,
                event_type=event_type,
                event_time=event_time,
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
                created_at=datetime.datetime.utcnow(),
            )
            session.add(event)
            await session.commit()

        return event_id

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
            result = await session.execute(
                sqlalchemy.select(EventLog).where(EventLog.event_id == event_id)
            )
            row = result.scalars().first()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def page_events(
        self,
        conversation_id: str | None = None,
        event_types: list[str] | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, typing.Any]], int | None, bool]:
        """Page through event records.

        Args:
            conversation_id: Filter by conversation ID
            event_types: Filter by event types
            before_seq: Get events before this sequence number
            limit: Maximum items to return (capped at 100)

        Returns:
            Tuple of (items, next_seq, has_more)
        """
        limit = min(limit, 100)  # Hard cap

        async with self._session_factory() as session:
            query = sqlalchemy.select(EventLog)

            if conversation_id is not None:
                query = query.where(EventLog.conversation_id == conversation_id)

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
    ) -> bool:
        """Check if there are events before a sequence number.

        Args:
            conversation_id: Conversation ID
            seq: Sequence number

        Returns:
            True if there are events before
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(EventLog)
                .where(
                    EventLog.conversation_id == conversation_id,
                    EventLog.id < seq,
                )
            )
            count = result.scalar()
            return count > 0

    def _row_to_dict(self, row: EventLog) -> dict[str, typing.Any]:
        """Convert an EventLog row to dict."""
        return {
            'id': row.id,
            'event_id': row.event_id,
            'event_type': row.event_type,
            'event_time': int(row.event_time.timestamp()) if row.event_time else None,
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
            'created_at': int(row.created_at.timestamp()) if row.created_at else None,
            'metadata': json.loads(row.metadata_json) if row.metadata_json else {},
        }
