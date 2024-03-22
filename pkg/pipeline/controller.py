from __future__ import annotations

import asyncio
import typing
import traceback

from ..core import app, entities
from . import entities as pipeline_entities
from ..plugin import events


class Controller:
    """总控制器
    """
    ap: app.Application

    semaphore: asyncio.Semaphore = None
    """请求并发控制信号量"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.semaphore = asyncio.Semaphore(self.ap.system_cfg.data['pipeline-concurrency'])

    async def consumer(self):
        """事件处理循环
        """
        try:
            while True:
                selected_query: entities.Query = None

                # 取请求
                async with self.ap.query_pool:
                    queries: list[entities.Query] = self.ap.query_pool.queries

                    for query in queries:
                        session = await self.ap.sess_mgr.get_session(query)
                        self.ap.logger.debug(f"Checking query {query} session {session}")

                        if not session.semaphore.locked():
                            selected_query = query
                            await session.semaphore.acquire()

                            break

                    if selected_query:  # 找到了
                        queries.remove(selected_query)
                    else:  # 没找到 说明：没有请求 或者 所有query对应的session都已达到并发上限
                        await self.ap.query_pool.condition.wait()
                        continue

                if selected_query:
                    async def _process_query(selected_query):
                        async with self.semaphore:  # 总并发上限
                            await self.process_query(selected_query)
                        
                        async with self.ap.query_pool:
                            (await self.ap.sess_mgr.get_session(selected_query)).semaphore.release()
                            # 通知其他协程，有新的请求可以处理了
                            self.ap.query_pool.condition.notify_all()
                    
                    asyncio.create_task(_process_query(selected_query))
        except Exception as e:
            # traceback.print_exc()
            self.ap.logger.error(f"控制器循环出错: {e}")
            self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")

    async def _check_output(self, query: entities.Query, result: pipeline_entities.StageProcessResult):
        """检查输出
        """
        if result.user_notice:
            await self.ap.platform_mgr.send(
                query.message_event,
                result.user_notice,
                query.adapter
            )
        if result.debug_notice:
            self.ap.logger.debug(result.debug_notice)
        if result.console_notice:
            self.ap.logger.info(result.console_notice)
        if result.error_notice:
            self.ap.logger.error(result.error_notice)

    async def _execute_from_stage(
        self,
        stage_index: int,
        query: entities.Query,
    ):
        """从指定阶段开始执行，实现了责任链模式和基于生成器的阶段分叉功能。

        如何看懂这里为什么这么写？
        去问 GPT-4:
            Q1: 现在有一个责任链，其中有多个stage，query对象在其中传递，stage.process可能返回Result也有可能返回typing.AsyncGenerator[Result, None]，
                如果返回的是生成器，需要挨个生成result，检查是否result中是否要求继续，如果要求继续就进行下一个stage。如果此次生成器产生的result处理完了，就继续生成下一个result，
                调用后续的stage，直到该生成器全部生成完。责任链中可能有多个stage会返回生成器
            Q2: 不是这样的，你可能理解有误。如果我们责任链上有这些Stage：

                A B C D E F G

                如果所有的stage都返回Result，且所有Result都要求继续，那么执行顺序是：

                A B C D E F G

                现在假设C返回的是AsyncGenerator，那么执行顺序是：

                A B C D E F G C D E F G C D E F G ...
            Q3: 但是如果不止一个stage会返回生成器呢？
        """
        i = stage_index

        while i < len(self.ap.stage_mgr.stage_containers):
            stage_container = self.ap.stage_mgr.stage_containers[i]
            
            result = stage_container.inst.process(query, stage_container.inst_name)

            if isinstance(result, typing.Coroutine):
                result = await result

            if isinstance(result, pipeline_entities.StageProcessResult):  # 直接返回结果
                self.ap.logger.debug(f"Stage {stage_container.inst_name} processed query {query} res {result}")
                await self._check_output(query, result)

                if result.result_type == pipeline_entities.ResultType.INTERRUPT:
                    self.ap.logger.debug(f"Stage {stage_container.inst_name} interrupted query {query}")
                    break
                elif result.result_type == pipeline_entities.ResultType.CONTINUE:
                    query = result.new_query
            elif isinstance(result, typing.AsyncGenerator):  # 生成器
                self.ap.logger.debug(f"Stage {stage_container.inst_name} processed query {query} gen")

                async for sub_result in result:
                    self.ap.logger.debug(f"Stage {stage_container.inst_name} processed query {query} res {sub_result}")
                    await self._check_output(query, sub_result)

                    if sub_result.result_type == pipeline_entities.ResultType.INTERRUPT:
                        self.ap.logger.debug(f"Stage {stage_container.inst_name} interrupted query {query}")
                        break
                    elif sub_result.result_type == pipeline_entities.ResultType.CONTINUE:
                        query = sub_result.new_query
                        await self._execute_from_stage(i + 1, query)
                break

            i += 1

    async def process_query(self, query: entities.Query):
        """处理请求
        """
        self.ap.logger.debug(f"Processing query {query}")

        try:
            await self._execute_from_stage(0, query)
        except Exception as e:
            self.ap.logger.error(f"处理请求时出错 query_id={query.query_id}: {e}")
            self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")
            # traceback.print_exc()
        finally:
            self.ap.logger.debug(f"Query {query} processed")

    async def run(self):
        """运行控制器
        """
        await self.consumer()
