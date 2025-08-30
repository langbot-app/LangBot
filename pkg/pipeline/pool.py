from __future__ import annotations

import asyncio
import typing

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter


class QueryPool:
    """请求池，请求获得调度进入pipeline之前，保存在这里"""

    query_id_counter: int = 0

    pool_lock: asyncio.Lock

    queries: list[pipeline_query.Query]

    cached_queries: dict[int, pipeline_query.Query]
    """Cached queries, used for plugin backward api call, will be removed after the query completely processed"""

    condition: asyncio.Condition

    def __init__(self):
        self.query_id_counter = 0
        self.pool_lock = asyncio.Lock()
        self.queries = []
        self.cached_queries = {}
        self.condition = asyncio.Condition(self.pool_lock)

    async def add_query(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: typing.Union[int, str],
        sender_id: typing.Union[int, str],
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid: typing.Optional[str] = None,
    ) -> pipeline_query.Query:
        async with self.condition:
            query_id = self.query_id_counter
            query = pipeline_query.Query(
                bot_uuid=bot_uuid,
                query_id=query_id,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                message_event=message_event,
                message_chain=message_chain,
                variables={},
                resp_messages=[],
                resp_message_chain=[],
                adapter=adapter,
                pipeline_uuid=pipeline_uuid,
            )
            self.queries.append(query)
            self.cached_queries[query_id] = query
            self.query_id_counter += 1
            self.condition.notify_all()

    async def __aenter__(self):
        await self.pool_lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.pool_lock.release()
