from __future__ import annotations

import asyncio
import typing

from ..core import entities
from ..platform import adapter as msadapter
from ..platform.types import message as platform_message
from ..platform.types import events as platform_events


class QueryPool:
    """请求池，请求获得调度进入pipeline之前，保存在这里"""

    query_id_counter: int = 0

    pool_lock: asyncio.Lock

    queries: list[entities.Query]

    condition: asyncio.Condition

    def __init__(self):
        self.query_id_counter = 0
        self.pool_lock = asyncio.Lock()
        self.queries = []
        self.condition = asyncio.Condition(self.pool_lock)

    async def add_query(
        self,
        launcher_type: entities.LauncherTypes,
        launcher_id: typing.Union[int, str],
        sender_id: typing.Union[int, str],
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        adapter: msadapter.MessagePlatformAdapter
    ) -> entities.Query:
        async with self.condition:
            query = entities.Query(
                query_id=self.query_id_counter,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                message_event=message_event,
                message_chain=message_chain,
                resp_messages=[],
                resp_message_chain=[],
                adapter=adapter
            )
            self.queries.append(query)
            self.query_id_counter += 1
            self.condition.notify_all()

    async def __aenter__(self):
        await self.pool_lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.pool_lock.release()
