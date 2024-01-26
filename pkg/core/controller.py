from __future__ import annotations

import asyncio
import traceback

from . import app, entities
from ..pipeline import entities as pipeline_entities

DEFAULT_QUERY_CONCURRENCY = 10


class Controller:
    """总控制器
    """
    ap: app.Application

    semaphore: asyncio.Semaphore = None
    """请求并发控制信号量"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.semaphore = asyncio.Semaphore(DEFAULT_QUERY_CONCURRENCY)

    async def consumer(self):
        """事件处理循环
        """
        while True:
            selected_query: entities.Query = None

            # 取请求
            async with self.ap.query_pool:
                queries: list[entities.Query] = self.ap.query_pool.queries

                if queries:
                    selected_query = queries.pop(0)  # FCFS
                else:
                    await self.ap.query_pool.condition.wait()
                    continue

            if selected_query:
                async def _process_query(selected_query):
                    async with self.semaphore:
                        await self.process_query(selected_query)
                
                asyncio.create_task(_process_query(selected_query))

    async def process_query(self, query: entities.Query):
        """处理请求
        """
        self.ap.logger.debug(f"Processing query {query}")

        try:
            for stage_container in self.ap.stage_mgr.stage_containers:
                res = await stage_container.inst.process(query, stage_container.inst_name)

                self.ap.logger.debug(f"Stage {stage_container.inst_name} res {res}")

                if res.user_notice:
                    await self.ap.im_mgr.send(
                        query.message_event,
                        res.user_notice
                    )
                if res.debug_notice:
                    self.ap.logger.debug(res.debug_notice)
                if res.console_notice:
                    self.ap.logger.info(res.console_notice)

                if res.result_type == pipeline_entities.ResultType.INTERRUPT:
                    self.ap.logger.debug(f"Stage {stage_container.inst_name} interrupted query {query}")
                    break
                elif res.result_type == pipeline_entities.ResultType.CONTINUE:
                    query = res.new_query
                    continue

        except Exception as e:
            self.ap.logger.error(f"处理请求时出错 {query}: {e}")
            traceback.print_exc()
        finally:
            self.ap.logger.debug(f"Query {query} processed")

    async def run(self):
        """运行控制器
        """
        await self.consumer()
