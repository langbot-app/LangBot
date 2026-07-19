from __future__ import annotations

import asyncio
import traceback

from ..core import app
from ..core import entities as core_entities
from ..workspace.errors import WorkspaceError, WorkspaceInvariantError

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from .pool import get_query_execution_context


class Controller:
    """总控制器"""

    ap: app.Application

    semaphore: asyncio.Semaphore = None
    """请求并发控制信号量"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.semaphore = asyncio.Semaphore(self.ap.instance_config.data['concurrency']['pipeline'])

    async def _assert_query_execution_active(
        self,
        query: pipeline_query.Query,
    ):
        """Revalidate a queued query immediately before runtime work starts."""

        execution_context = get_query_execution_context(query)
        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise WorkspaceInvariantError('Queued query instance does not match the active Workspace binding')
        return execution_context

    async def _process_query(self, selected_query: pipeline_query.Query) -> None:
        """Run one selected query and always release its scheduling slot."""

        try:
            async with self.semaphore:
                execution_context = await self._assert_query_execution_active(selected_query)
                pipeline_uuid = selected_query.pipeline_uuid

                if pipeline_uuid:
                    pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(
                        execution_context,
                        pipeline_uuid,
                    )
                    if pipeline:
                        await pipeline.run(selected_query)
                    else:
                        self.ap.logger.warning(
                            f'Pipeline {pipeline_uuid} not found for query {selected_query.query_id}, query dropped'
                        )
                else:
                    self.ap.logger.warning(f'No pipeline_uuid for query {selected_query.query_id}, query dropped')
        except WorkspaceError as exc:
            self.ap.logger.info(
                f'Dropped query {selected_query.query_id} because its Workspace execution binding is stale: {exc}'
            )
        finally:
            await self.ap.query_pool.remove_query(selected_query)
            async with self.ap.query_pool:
                (await self.ap.sess_mgr.get_session(selected_query))._semaphore.release()
                self.ap.query_pool.condition.notify_all()

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
                        # Debug logging removed from tight loop to prevent excessive log generation
                        # that can cause memory overflow in high-traffic scenarios

                        if not session._semaphore.locked():
                            selected_query = query
                            await session._semaphore.acquire()
                            # Only log when actually selecting a query
                            self.ap.logger.debug(f'Selected query {query.query_id} for processing')

                            break

                    if selected_query:  # 找到了
                        queries.remove(selected_query)
                    else:  # 没找到 说明：没有请求 或者 所有query对应的session都已达到并发上限
                        await self.ap.query_pool.condition.wait()
                        continue

                if selected_query:
                    execution_context = get_query_execution_context(selected_query)
                    self.ap.task_mgr.create_task(
                        self._process_query(selected_query),
                        kind='query',
                        name=f'query-{selected_query.query_id}',
                        scopes=[
                            core_entities.LifecycleControlScope.APPLICATION,
                            core_entities.LifecycleControlScope.PLATFORM,
                        ],
                        instance_uuid=execution_context.instance_uuid,
                        workspace_uuid=execution_context.workspace_uuid,
                        placement_generation=execution_context.placement_generation,
                    )

        except Exception as e:
            # traceback.print_exc()
            self.ap.logger.error(f'控制器循环出错: {e}')
            self.ap.logger.error(f'Traceback: {traceback.format_exc()}')

    async def run(self):
        """运行控制器"""
        await self.consumer()
