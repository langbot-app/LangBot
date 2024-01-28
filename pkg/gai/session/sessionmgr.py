from __future__ import annotations

import asyncio

from ...core import app, entities as core_entities
from . import entities


class SessionManager:

    ap: app.Application

    session_list: list[entities.Session]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.session_list = []

    async def initialize(self):
        pass

    async def get_session(self, query: core_entities.Query) -> entities.Session:
        """获取会话
        """
        for session in self.session_list:
            if query.launcher_type == session.launcher_type and query.launcher_id == session.launcher_id:
                return session

        session = entities.Session(
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
            semaphore=asyncio.Semaphore(1) if self.ap.cfg_mgr.data['wait_last_done'] else asyncio.Semaphore(10000),
        )
        self.session_list.append(session)
        return session

    async def get_conversation(self, session: entities.Session) -> entities.Conversation:
        if not session.conversations:
            session.conversations = []

        if session.using_conversation is None:
            conversation = entities.Conversation(
                prompt=await self.ap.prompt_mgr.get_prompt(session.use_prompt_name),
                messages=[],
                use_model=await self.ap.model_mgr.get_model_by_name(self.ap.cfg_mgr.data['completion_api_params']['model']),
                use_funcs=await self.ap.tool_mgr.get_all_functions(),
            )
            session.conversations.append(conversation)
            session.using_conversation = conversation

        return session.using_conversation
