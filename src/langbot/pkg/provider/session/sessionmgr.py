from __future__ import annotations

import asyncio

from ...core import app
from langbot_plugin.api.entities.builtin.provider import message as provider_message, prompt as provider_prompt
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class SessionManager:
    """会话管理器"""

    ap: app.Application

    session_list: list[provider_session.Session]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.session_list = []

    async def initialize(self):
        pass

    async def get_session(self, query: pipeline_query.Query) -> provider_session.Session:
        """获取会话"""
        for session in self.session_list:
            if query.launcher_type == session.launcher_type and query.launcher_id == session.launcher_id:
                return session

        session_concurrency = self.ap.instance_config.data['concurrency']['session']

        session = provider_session.Session(
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
        )
        session._semaphore = asyncio.Semaphore(session_concurrency)
        self.session_list.append(session)
        return session

    async def get_conversation(
        self,
        query: pipeline_query.Query,
        session: provider_session.Session,
        prompt_config: list[dict],
        pipeline_uuid: str,
        bot_uuid: str,
    ) -> provider_session.Conversation:
        """获取对话或创建对话"""

        if not session.conversations:
            session.conversations = []

        # set prompt
        prompt_messages = []

        for prompt_message in prompt_config:
            prompt_messages.append(provider_message.Message(**prompt_message))

        prompt = provider_prompt.Prompt(
            name='default',
            messages=prompt_messages,
        )

        if session.using_conversation is None or session.using_conversation.pipeline_uuid != pipeline_uuid:
            conversation = provider_session.Conversation(
                prompt=prompt,
                messages=[],
                pipeline_uuid=pipeline_uuid,
                bot_uuid=bot_uuid,
            )
            session.conversations.append(conversation)
            session.using_conversation = conversation

        return session.using_conversation
