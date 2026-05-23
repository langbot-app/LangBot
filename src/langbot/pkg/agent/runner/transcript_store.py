"""Transcript store for writing and querying conversation history."""
from __future__ import annotations

import json
import datetime
import typing
import uuid

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...entity.persistence.transcript import Transcript


class TranscriptStore:
    """Store for Transcript records.

    Handles writing transcript items and querying them for history API.
    All methods are async and use the provided database engine.
    """

    engine: AsyncEngine

    # Hard limits
    MAX_CONTENT_LENGTH = 4000
    HARD_LIMIT = 100

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    async def append_transcript(
        self,
        transcript_id: str | None,
        event_id: str,
        conversation_id: str,
        role: str,
        content: str | None = None,
        content_json: dict[str, typing.Any] | None = None,
        artifact_refs: list[dict[str, typing.Any]] | None = None,
        thread_id: str | None = None,
        item_type: str = "message",
        run_id: str | None = None,
        runner_id: str | None = None,
        metadata: dict[str, typing.Any] | None = None,
    ) -> str:
        """Append a transcript item.

        Args:
            transcript_id: Unique transcript ID (generated if None)
            event_id: Source event ID
            conversation_id: Conversation ID
            role: Message role (user, assistant, system, tool)
            content: Text content
            content_json: Full structured content
            artifact_refs: Artifact references
            thread_id: Thread ID
            item_type: Item type
            run_id: Run ID that generated this
            runner_id: Runner ID that generated this
            metadata: Additional metadata

        Returns:
            The transcript_id
        """
        if transcript_id is None:
            transcript_id = str(uuid.uuid4())

        # Truncate content if too long
        if content and len(content) > self.MAX_CONTENT_LENGTH:
            content = content[:self.MAX_CONTENT_LENGTH - 3] + "..."

        # Get next sequence number for this conversation
        seq = await self._get_next_seq(conversation_id)

        async with self._session_factory() as session:
            item = Transcript(
                transcript_id=transcript_id,
                event_id=event_id,
                conversation_id=conversation_id,
                thread_id=thread_id,
                role=role,
                item_type=item_type,
                content=content,
                content_json=json.dumps(content_json) if content_json else None,
                artifact_refs_json=json.dumps(artifact_refs) if artifact_refs else None,
                seq=seq,
                run_id=run_id,
                runner_id=runner_id,
                created_at=datetime.datetime.utcnow(),
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            session.add(item)
            await session.commit()

        return transcript_id

    async def page_transcript(
        self,
        conversation_id: str,
        before_seq: int | None = None,
        after_seq: int | None = None,
        limit: int = 50,
        direction: str = "backward",
        include_artifacts: bool = False,
    ) -> tuple[list[dict[str, typing.Any]], int | None, int | None, bool]:
        """Page through transcript items.

        Args:
            conversation_id: Conversation ID
            before_seq: Get items before this sequence (backward)
            after_seq: Get items after this sequence (forward)
            limit: Maximum items to return (capped at 100)
            direction: 'backward' (older) or 'forward' (newer)
            include_artifacts: Include artifact refs

        Returns:
            Tuple of (items, next_seq, prev_seq, has_more)
        """
        limit = min(limit, self.HARD_LIMIT)

        async with self._session_factory() as session:
            query = sqlalchemy.select(Transcript).where(
                Transcript.conversation_id == conversation_id
            )

            if direction == "backward" and before_seq is not None:
                query = query.where(Transcript.seq < before_seq)
                query = query.order_by(Transcript.seq.desc())
            elif direction == "forward" and after_seq is not None:
                query = query.where(Transcript.seq > after_seq)
                query = query.order_by(Transcript.seq.asc())
            else:
                # Default: most recent items first (backward from latest)
                query = query.order_by(Transcript.seq.desc())

            query = query.limit(limit + 1)

            result = await session.execute(query)
            rows = result.scalars().all()

            items = [self._row_to_dict(row, include_artifacts) for row in rows[:limit]]
            has_more = len(rows) > limit

            # Calculate cursors
            next_seq = None
            prev_seq = None

            if direction == "backward":
                # Items are in descending order
                if items:
                    next_seq = items[-1].get('seq') if has_more else None
                    prev_seq = items[0].get('seq')
            else:
                # Items are in ascending order
                if items:
                    next_seq = items[-1].get('seq') if has_more else None
                    prev_seq = items[0].get('seq')

            return items, next_seq, prev_seq, has_more

    async def search_transcript(
        self,
        conversation_id: str,
        query_text: str,
        filters: dict[str, typing.Any] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, typing.Any]]:
        """Search transcript items.

        Basic implementation using LIKE filtering.

        Args:
            conversation_id: Conversation ID
            query_text: Search query
            filters: Optional filters
            top_k: Maximum results

        Returns:
            List of matching items
        """
        async with self._session_factory() as session:
            query = sqlalchemy.select(Transcript).where(
                Transcript.conversation_id == conversation_id,
                Transcript.content.ilike(f"%{query_text}%"),
            )

            # Apply additional filters
            if filters:
                if 'roles' in filters:
                    query = query.where(Transcript.role.in_(filters['roles']))
                if 'item_types' in filters:
                    query = query.where(Transcript.item_type.in_(filters['item_types']))

            query = query.order_by(Transcript.seq.desc()).limit(top_k)

            result = await session.execute(query)
            rows = result.scalars().all()

            return [self._row_to_dict(row, include_artifacts=True) for row in rows]

    async def get_latest_cursor(
        self,
        conversation_id: str,
    ) -> str | None:
        """Get the latest cursor for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Cursor string (seq number), or None if no items
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(Transcript.seq)
                .where(Transcript.conversation_id == conversation_id)
                .order_by(Transcript.seq.desc())
                .limit(1)
            )
            row = result.scalars().first()
            if row is None:
                return None
            return str(row)

    async def has_history_before(
        self,
        conversation_id: str,
        seq: int,
    ) -> bool:
        """Check if there is history before a sequence number.

        Args:
            conversation_id: Conversation ID
            seq: Sequence number

        Returns:
            True if there are items before
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(Transcript)
                .where(
                    Transcript.conversation_id == conversation_id,
                    Transcript.seq < seq,
                )
            )
            count = result.scalar()
            return count > 0

    async def _get_next_seq(self, conversation_id: str) -> int:
        """Get the next sequence number for a conversation."""
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(sqlalchemy.func.max(Transcript.seq))
                .where(Transcript.conversation_id == conversation_id)
            )
            max_seq = result.scalar()
            return (max_seq or 0) + 1

    def _row_to_dict(
        self,
        row: Transcript,
        include_artifacts: bool = False,
    ) -> dict[str, typing.Any]:
        """Convert a Transcript row to dict."""
        result = {
            'transcript_id': row.transcript_id,
            'event_id': row.event_id,
            'conversation_id': row.conversation_id,
            'thread_id': row.thread_id,
            'role': row.role,
            'item_type': row.item_type,
            'content': row.content,
            'content_json': json.loads(row.content_json) if row.content_json else None,
            'seq': row.seq,
            'cursor': str(row.seq),
            'created_at': int(row.created_at.timestamp()) if row.created_at else None,
            'metadata': json.loads(row.metadata_json) if row.metadata_json else {},
        }

        if include_artifacts and row.artifact_refs_json:
            result['artifact_refs'] = json.loads(row.artifact_refs_json)
        else:
            result['artifact_refs'] = []

        return result
