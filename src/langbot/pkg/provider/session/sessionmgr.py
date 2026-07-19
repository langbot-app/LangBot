from __future__ import annotations

import asyncio
import dataclasses

from langbot_plugin.api.entities.builtin.provider import message as provider_message, prompt as provider_prompt
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from ...api.http.context import ExecutionContext
from ...core import app
from ...pipeline.pool import (
    ExecutionContextMismatchError,
    ExecutionContextRequiredError,
    bind_execution_context,
    get_query_execution_context,
)

SessionKey = tuple[
    str,
    str,
    int,
    str,
    str,
    int | str,
]


def _query_session_key(query: pipeline_query.Query) -> tuple[SessionKey, ExecutionContext]:
    execution_context = get_query_execution_context(query)
    bot_uuid = getattr(query, 'bot_uuid', None)
    if not isinstance(bot_uuid, str) or not bot_uuid.strip():
        raise ExecutionContextRequiredError('Query.bot_uuid is required for session lookup')

    execution_context = bind_execution_context(execution_context, bot_uuid=bot_uuid)
    key: SessionKey = (
        execution_context.instance_uuid,
        execution_context.workspace_uuid,
        execution_context.placement_generation,
        bot_uuid,
        query.launcher_type.value,
        query.launcher_id,
    )
    return key, execution_context


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
        session_key, execution_context = _query_session_key(query)
        for session in self.session_list:
            if getattr(session, '_langbot_session_key', None) == session_key:
                return session

        session_concurrency = self.ap.instance_config.data['concurrency']['session']

        session = provider_session.Session(
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
            bot_uuid=query.bot_uuid,
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
        )
        session_context = dataclasses.replace(
            execution_context,
            pipeline_uuid=None,
            query_uuid=None,
        )
        # langbot-plugin 0.4.13 ignores Workspace fields. Preserve them until
        # the Workspace-aware SDK becomes the minimum supported version.
        object.__setattr__(session, 'instance_uuid', session_context.instance_uuid)
        object.__setattr__(session, 'workspace_uuid', session_context.workspace_uuid)
        object.__setattr__(
            session,
            'placement_generation',
            session_context.placement_generation,
        )
        object.__setattr__(session, 'bot_uuid', query.bot_uuid)
        object.__setattr__(session, '_execution_context', session_context)
        object.__setattr__(session, '_langbot_session_key', session_key)
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

        session_key, execution_context = _query_session_key(query)
        if getattr(session, '_langbot_session_key', None) != session_key:
            raise ExecutionContextMismatchError('Session does not belong to the Query execution scope')
        execution_context = bind_execution_context(
            execution_context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
        )
        if execution_context.bot_uuid != getattr(session, 'bot_uuid', None):
            raise ExecutionContextMismatchError('Session bot_uuid does not match the Query execution scope')

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

        if (
            session.using_conversation is None
            or session.using_conversation.pipeline_uuid != pipeline_uuid
            or session.using_conversation.bot_uuid != bot_uuid
        ):
            conversation = provider_session.Conversation(
                prompt=prompt,
                messages=[],
                pipeline_uuid=pipeline_uuid,
                bot_uuid=bot_uuid,
            )
            session.conversations.append(conversation)
            session.using_conversation = conversation

        return session.using_conversation
