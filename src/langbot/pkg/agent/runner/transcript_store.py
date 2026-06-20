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
from langbot_plugin.api.entities.builtin.provider import message as provider_message


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
        bot_id: str | None = None,
        workspace_id: str | None = None,
        content: str | None = None,
        content_json: dict[str, typing.Any] | None = None,
        attachment_refs: list[dict[str, typing.Any]] | None = None,
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
            bot_id: Bot UUID scope
            workspace_id: Workspace scope
            content: Text content
            content_json: Full structured content
            attachment_refs: Attachment references
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

        async with self._session_factory() as session:
            item = Transcript(
                transcript_id=transcript_id,
                event_id=event_id,
                bot_id=bot_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                thread_id=thread_id,
                role=role,
                item_type=item_type,
                content=content,
                content_json=json.dumps(content_json) if content_json else None,
                attachment_refs_json=json.dumps(attachment_refs) if attachment_refs else None,
                seq=0,
                run_id=run_id,
                runner_id=runner_id,
                created_at=_utc_now(),
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            session.add(item)
            await session.flush()
            item.seq = item.id or await self._get_next_seq(conversation_id)
            await session.commit()

        return transcript_id

    async def page_transcript(
        self,
        conversation_id: str,
        before_seq: int | None = None,
        after_seq: int | None = None,
        limit: int = 50,
        direction: str = "backward",
        include_attachments: bool = False,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> tuple[list[dict[str, typing.Any]], int | None, int | None, bool]:
        """Page through transcript items.

        Args:
            conversation_id: Conversation ID
            before_seq: Get items before this sequence (backward)
            after_seq: Get items after this sequence (forward)
            limit: Maximum items to return (capped at 100)
            direction: 'backward' (older) or 'forward' (newer)
            include_attachments: Include attachment refs
            bot_id: Optional bot scope filter
            workspace_id: Optional workspace scope filter
            thread_id: Optional thread scope filter
            strict_thread: When true, require thread_id equality including NULL

        Returns:
            Tuple of (items, next_seq, prev_seq, has_more)
        """
        limit = min(limit, self.HARD_LIMIT)

        async with self._session_factory() as session:
            query = sqlalchemy.select(Transcript).where(
                Transcript.conversation_id == conversation_id
            )
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)

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

            items = [self._row_to_dict(row, include_attachments) for row in rows[:limit]]
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
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> list[dict[str, typing.Any]]:
        """Search transcript items.

        Basic implementation using LIKE filtering.

        Args:
            conversation_id: Conversation ID
            query_text: Search query
            filters: Optional filters
            top_k: Maximum results
            bot_id: Optional bot scope filter
            workspace_id: Optional workspace scope filter
            thread_id: Optional thread scope filter
            strict_thread: When true, require thread_id equality including NULL

        Returns:
            List of matching items
        """
        async with self._session_factory() as session:
            query = sqlalchemy.select(Transcript).where(
                Transcript.conversation_id == conversation_id,
                Transcript.content.ilike(f"%{query_text}%"),
            )
            query = self._apply_scope_filters(query, bot_id, workspace_id, thread_id, strict_thread)

            # Apply additional filters
            if filters:
                if 'roles' in filters:
                    query = query.where(Transcript.role.in_(filters['roles']))
                if 'item_types' in filters:
                    query = query.where(Transcript.item_type.in_(filters['item_types']))

            query = query.order_by(Transcript.seq.desc()).limit(top_k)

            result = await session.execute(query)
            rows = result.scalars().all()

            return [self._row_to_dict(row, include_attachments=True) for row in rows]

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

    async def get_legacy_provider_messages(
        self,
        conversation_id: str,
        limit: int = HARD_LIMIT,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> list[provider_message.Message]:
        """Project Transcript rows into the legacy provider Message view.

        AgentRunner history is canonical in Transcript. This view exists for
        legacy Pipeline readers such as PromptPreProcessing that still expect
        query.messages.
        """
        items, _, _, _ = await self.page_transcript(
            conversation_id=conversation_id,
            limit=limit,
            direction="backward",
            bot_id=bot_id,
            workspace_id=workspace_id,
            thread_id=thread_id,
            strict_thread=strict_thread,
        )

        messages: list[provider_message.Message] = []
        for item in reversed(items):
            message = self._transcript_item_to_provider_message(item)
            if message is not None:
                messages.append(message)
        return messages

    async def has_history_before(
        self,
        conversation_id: str,
        seq: int,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        strict_thread: bool = False,
    ) -> bool:
        """Check if there is history before a sequence number.

        Args:
            conversation_id: Conversation ID
            seq: Sequence number

        Returns:
            True if there are items before
        """
        async with self._session_factory() as session:
            query = (
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(Transcript)
                .where(Transcript.conversation_id == conversation_id, Transcript.seq < seq)
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
            query = query.where(Transcript.bot_id == bot_id)
        if workspace_id is not None:
            query = query.where(Transcript.workspace_id == workspace_id)
        if strict_thread:
            if thread_id is None:
                query = query.where(Transcript.thread_id.is_(None))
            else:
                query = query.where(Transcript.thread_id == thread_id)
        return query

    async def cleanup_transcripts_older_than(
        self,
        before: datetime.datetime,
    ) -> int:
        """Delete Transcript rows created before the supplied timestamp."""
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.delete(Transcript).where(Transcript.created_at < before)
            )
            await session.commit()
            return result.rowcount or 0

    async def _get_next_seq(self, conversation_id: str) -> int:
        """Fallback next sequence number for stores that cannot expose autoincrement IDs."""
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
        include_attachments: bool = False,
    ) -> dict[str, typing.Any]:
        """Convert a Transcript row to dict."""
        result = {
            'transcript_id': row.transcript_id,
            'event_id': row.event_id,
            'bot_id': row.bot_id,
            'workspace_id': row.workspace_id,
            'conversation_id': row.conversation_id,
            'thread_id': row.thread_id,
            'role': row.role,
            'item_type': row.item_type,
            'content': row.content,
            'content_json': json.loads(row.content_json) if row.content_json else None,
            'seq': row.seq,
            'cursor': str(row.seq),
            'created_at': _datetime_to_epoch(row.created_at),
            'metadata': json.loads(row.metadata_json) if row.metadata_json else {},
        }

        if include_attachments and row.attachment_refs_json:
            result['attachment_refs'] = json.loads(row.attachment_refs_json)
        else:
            result['attachment_refs'] = []

        return result

    def _transcript_item_to_provider_message(
        self,
        item: dict[str, typing.Any],
    ) -> provider_message.Message | None:
        """Convert one Transcript API item into a provider Message."""
        if item.get('item_type') != 'message':
            return None

        role = item.get('role')
        if role not in {'user', 'assistant'}:
            return None

        content_json = item.get('content_json')
        if isinstance(content_json, dict):
            message_data = dict(content_json)
            message_data['role'] = role
            try:
                return provider_message.Message.model_validate(message_data)
            except Exception:
                pass

        content = item.get('content')
        if content is None:
            return None
        return provider_message.Message(role=role, content=content)
