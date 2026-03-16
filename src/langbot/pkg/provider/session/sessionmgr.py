from __future__ import annotations

import asyncio
import time

from ...core import app
from langbot_plugin.api.entities.builtin.provider import message as provider_message, prompt as provider_prompt
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class SessionManager:
    """Conversation session manager."""

    ap: app.Application

    session_list: list[provider_session.Session]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.session_list = []
        self._last_active_at: dict[str, float] = {}

    async def initialize(self):
        pass

    @staticmethod
    def _build_session_key(launcher_type, launcher_id) -> str:
        launcher_type_value = launcher_type.value if hasattr(launcher_type, 'value') else str(launcher_type)
        return f'{launcher_type_value}:{launcher_id}'

    def _touch_session(self, session: provider_session.Session) -> None:
        self._last_active_at[self._build_session_key(session.launcher_type, session.launcher_id)] = time.time()

    async def get_session(self, query: pipeline_query.Query) -> provider_session.Session:
        """Get or create a session."""
        for session in self.session_list:
            if query.launcher_type == session.launcher_type and query.launcher_id == session.launcher_id:
                self._touch_session(session)
                return session

        session_concurrency = self.ap.instance_config.data['concurrency']['session']

        session = provider_session.Session(
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
        )
        session._semaphore = asyncio.Semaphore(session_concurrency)
        self.session_list.append(session)
        self._touch_session(session)
        return session

    async def get_conversation(
        self,
        query: pipeline_query.Query,
        session: provider_session.Session,
        prompt_config: list[dict],
        pipeline_uuid: str,
        bot_uuid: str,
    ) -> provider_session.Conversation:
        """Get or create the active conversation for a session."""

        if not session.conversations:
            session.conversations = []

        prompt_messages = [provider_message.Message(**prompt_message) for prompt_message in prompt_config]
        prompt = provider_prompt.Prompt(name='default', messages=prompt_messages)

        if session.using_conversation is None or session.using_conversation.pipeline_uuid != pipeline_uuid:
            conversation = provider_session.Conversation(
                prompt=prompt,
                messages=[],
                pipeline_uuid=pipeline_uuid,
                bot_uuid=bot_uuid,
            )
            session.conversations.append(conversation)
            session.using_conversation = conversation

        self._touch_session(session)
        return session.using_conversation

    def cleanup_inactive_sessions(self, max_idle_seconds: int) -> int:
        if max_idle_seconds <= 0:
            return 0

        now = time.time()
        kept_sessions: list[provider_session.Session] = []
        deleted = 0

        for session in self.session_list:
            session_key = self._build_session_key(session.launcher_type, session.launcher_id)
            last_active_at = self._last_active_at.get(session_key, now)
            semaphore = getattr(session, '_semaphore', None)
            is_locked = bool(semaphore and semaphore.locked())

            if is_locked or (now - last_active_at) < max_idle_seconds:
                kept_sessions.append(session)
                continue

            self._last_active_at.pop(session_key, None)
            deleted += 1

        self.session_list = kept_sessions
        return deleted
