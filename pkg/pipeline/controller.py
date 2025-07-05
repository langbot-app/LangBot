from __future__ import annotations

import asyncio
import traceback

from ..core import app
from ..core import entities as core_entities

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class Controller:
    """总控制器"""

    ap: app.Application

    semaphore: asyncio.Semaphore = None
    """请求并发控制信号量"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.semaphore = asyncio.Semaphore(self.ap.instance_config.data['concurrency']['pipeline'])

    async def consumer(self):
        """事件处理循环"""
        try:
            while True:
                selected_query: pipeline_query.Query = None

                # 取请求
                async with self.ap.query_pool:
                    queries: list[pipeline_query.Query] = self.ap.query_pool.queries

                    for query in queries:
                        session = await self.ap.sess_mgr.get_session(query)
                        self.ap.logger.debug(f'Checking query {query} session {session}')

                        if not session._semaphore.locked():
                            selected_query = query
                            await session._semaphore.acquire()

                            break

                    if selected_query:  # 找到了
                        queries.remove(selected_query)
                    else:  # 没找到 说明：没有请求 或者 所有query对应的session都已达到并发上限
                        await self.ap.query_pool.condition.wait()
                        continue

                if selected_query:

                    async def _process_query(selected_query: pipeline_query.Query):
                        async with self.semaphore:  # 总并发上限
                            # find pipeline
                            # Here firstly find the bot, then find the pipeline, in case the bot adapter's config is not the latest one.
                            # Like aiocqhttp, once a client is connected, even the adapter was updated and restarted, the existing client connection will not be affected.
                            pipeline_uuid = selected_query.pipeline_uuid

                            if pipeline_uuid:
                                pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
                                if pipeline:
                                    await pipeline.run(selected_query)

                        async with self.ap.query_pool:
                            (await self.ap.sess_mgr.get_session(selected_query))._semaphore.release()
                            # 通知其他协程，有新的请求可以处理了
                            self.ap.query_pool.condition.notify_all()

                    self.ap.task_mgr.create_task(
                        _process_query(selected_query),
                        kind='query',
                        name=f'query-{selected_query.query_id}',
                        scopes=[
                            core_entities.LifecycleControlScope.APPLICATION,
                            core_entities.LifecycleControlScope.PLATFORM,
                        ],
                    )

        except Exception as e:
            # traceback.print_exc()
            self.ap.logger.error(f'控制器循环出错: {e}')
            self.ap.logger.error(f'Traceback: {traceback.format_exc()}')

    async def run(self):
        """运行控制器"""
        await self.consumer()
