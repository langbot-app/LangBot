from __future__ import annotations

import uuid
import datetime
import json
import logging

import sqlalchemy

from ....core import app
from ....entity.persistence import human_takeover as persistence_human_takeover

import langbot_plugin.api.entities.builtin.platform.message as platform_message


class HumanTakeoverService:
    """Human takeover service.

    Manages operator takeover of user conversation sessions, bypassing
    the normal AI pipeline. Uses an in-memory cache for fast synchronous
    lookups on the hot message path, backed by database persistence.
    """

    ap: app.Application

    # In-memory cache: session_id -> HumanTakeoverSession record id
    # Only contains sessions with status='active'
    _active_sessions: dict[str, str]

    logger: logging.Logger

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._active_sessions = {}
        self.logger = logging.getLogger('human-takeover')

    async def initialize(self) -> None:
        """Load active takeover sessions from DB into memory cache."""
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_human_takeover.HumanTakeoverSession).where(
                    persistence_human_takeover.HumanTakeoverSession.status == 'active'
                )
            )
            rows = result.all()
            for row in rows:
                session = row[0] if isinstance(row, tuple) else row
                self._active_sessions[session.session_id] = session.id
            self.logger.info(f'Loaded {len(self._active_sessions)} active takeover sessions from DB')
        except Exception as e:
            self.logger.warning(f'Failed to load active takeover sessions: {e}')

    def is_taken_over(self, session_id: str) -> bool:
        """Check if a session is currently under human takeover.

        This is a synchronous in-memory lookup for performance, since it
        is called on every incoming message (hot path).
        """
        return session_id in self._active_sessions

    async def takeover_session(
        self,
        session_id: str,
        bot_uuid: str,
        taken_by: str | None = None,
        platform: str | None = None,
        user_id: str | None = None,
        user_name: str | None = None,
    ) -> dict:
        """Take over a conversation session.

        Args:
            session_id: The session to take over (e.g. 'person_123' or 'group_456').
            bot_uuid: UUID of the bot whose session is being taken over.
            taken_by: Email/username of the admin performing the takeover.
            platform: Platform name.
            user_id: The end-user's ID in the session.
            user_name: The end-user's display name.

        Returns:
            Dict with the created takeover session record.

        Raises:
            ValueError: If the session is already taken over.
        """
        if self.is_taken_over(session_id):
            raise ValueError(f'Session {session_id} is already taken over')

        record_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        record_data = {
            'id': record_id,
            'session_id': session_id,
            'bot_uuid': bot_uuid,
            'status': 'active',
            'taken_by': taken_by,
            'taken_at': now,
            'released_at': None,
            'platform': platform,
            'user_id': user_id,
            'user_name': user_name,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_human_takeover.HumanTakeoverSession).values(record_data)
        )

        # Update in-memory cache
        self._active_sessions[session_id] = record_id

        self.logger.info(f'Session {session_id} taken over by {taken_by}')

        return record_data

    async def release_session(self, session_id: str) -> dict:
        """Release a taken-over session back to AI pipeline processing.

        Args:
            session_id: The session to release.

        Returns:
            Dict with the updated takeover session record.

        Raises:
            ValueError: If the session is not currently taken over.
        """
        if not self.is_taken_over(session_id):
            raise ValueError(f'Session {session_id} is not currently taken over')

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_human_takeover.HumanTakeoverSession)
            .where(
                sqlalchemy.and_(
                    persistence_human_takeover.HumanTakeoverSession.session_id == session_id,
                    persistence_human_takeover.HumanTakeoverSession.status == 'active',
                )
            )
            .values(status='released', released_at=now)
        )

        # Remove from in-memory cache
        self._active_sessions.pop(session_id, None)

        self.logger.info(f'Session {session_id} released back to AI pipeline')

        return {
            'session_id': session_id,
            'status': 'released',
            'released_at': now.isoformat(),
        }

    async def send_message(
        self,
        session_id: str,
        message_text: str,
        operator_name: str | None = None,
    ) -> dict:
        """Send a message from the operator to the user via the platform adapter.

        Args:
            session_id: The taken-over session ID (e.g. 'person_123' or 'group_456').
            message_text: The text message to send.
            operator_name: Name of the operator sending the message.

        Returns:
            Dict with send result info.

        Raises:
            ValueError: If the session is not currently taken over.
            RuntimeError: If the bot or adapter cannot be found.
        """
        if not self.is_taken_over(session_id):
            raise ValueError(f'Session {session_id} is not currently taken over')

        # Look up the takeover record to get bot_uuid
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_human_takeover.HumanTakeoverSession).where(
                sqlalchemy.and_(
                    persistence_human_takeover.HumanTakeoverSession.session_id == session_id,
                    persistence_human_takeover.HumanTakeoverSession.status == 'active',
                )
            )
        )
        row = result.first()
        if not row:
            raise RuntimeError(f'Active takeover record not found for session {session_id}')

        takeover_record = row[0] if isinstance(row, tuple) else row
        bot_uuid = takeover_record.bot_uuid

        # Get the runtime bot
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if not runtime_bot:
            raise RuntimeError(f'Bot {bot_uuid} not found or not running')

        # Parse session_id to determine target_type and target_id
        # Format: 'person_{id}' or 'group_{id}'
        if session_id.startswith('person_'):
            target_type = 'person'
            target_id = session_id[len('person_') :]
        elif session_id.startswith('group_'):
            target_type = 'group'
            target_id = session_id[len('group_') :]
        else:
            raise ValueError(f'Invalid session_id format: {session_id}')

        # Build message chain
        message_chain = platform_message.MessageChain([platform_message.Plain(text=message_text)])

        # Send via adapter
        await runtime_bot.adapter.send_message(target_type, target_id, message_chain)

        # Record the operator message in monitoring
        bot_name = runtime_bot.bot_entity.name or bot_uuid
        try:
            message_content = json.dumps(message_chain.model_dump(), ensure_ascii=False)
        except Exception:
            message_content = message_text

        await self.ap.monitoring_service.record_message(
            bot_id=bot_uuid,
            bot_name=bot_name,
            pipeline_id='__human_takeover__',
            pipeline_name='Human Takeover',
            message_content=message_content,
            session_id=session_id,
            status='success',
            level='info',
            platform=takeover_record.platform,
            user_id=operator_name or 'operator',
            user_name=operator_name or 'Operator',
            role='operator',
        )

        self.logger.info(f'Operator message sent to session {session_id}: {message_text[:50]}...')

        return {
            'session_id': session_id,
            'message_sent': True,
        }

    async def get_active_sessions(
        self,
        bot_uuid: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get list of active (or all) takeover sessions.

        Args:
            bot_uuid: Optional filter by bot UUID.
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            Tuple of (list of session dicts, total count).
        """
        conditions = []

        if bot_uuid:
            conditions.append(persistence_human_takeover.HumanTakeoverSession.bot_uuid == bot_uuid)

        # Count
        count_query = sqlalchemy.select(sqlalchemy.func.count(persistence_human_takeover.HumanTakeoverSession.id))
        if conditions:
            count_query = count_query.where(sqlalchemy.and_(*conditions))

        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0

        # Fetch records
        query = sqlalchemy.select(persistence_human_takeover.HumanTakeoverSession).order_by(
            persistence_human_takeover.HumanTakeoverSession.taken_at.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(query)
        rows = result.all()

        sessions = []
        for row in rows:
            session = row[0] if isinstance(row, tuple) else row
            sessions.append(
                self.ap.persistence_mgr.serialize_model(persistence_human_takeover.HumanTakeoverSession, session)
            )

        return sessions, total

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Get detail for a specific takeover session.

        Args:
            session_id: The session ID to look up.

        Returns:
            Session dict or None if not found.
        """
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_human_takeover.HumanTakeoverSession)
            .where(persistence_human_takeover.HumanTakeoverSession.session_id == session_id)
            .order_by(persistence_human_takeover.HumanTakeoverSession.taken_at.desc())
        )
        row = result.first()
        if not row:
            return None

        session = row[0] if isinstance(row, tuple) else row
        return self.ap.persistence_mgr.serialize_model(persistence_human_takeover.HumanTakeoverSession, session)
