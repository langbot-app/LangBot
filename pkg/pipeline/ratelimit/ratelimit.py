from __future__ import annotations

import typing

from .. import entities, stage
from . import algo
from ...utils import importutil

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from . import algos

importutil.import_modules_in_pkg(algos)


@stage.stage_class('RequireRateLimitOccupancy')
@stage.stage_class('ReleaseRateLimitOccupancy')
class RateLimit(stage.PipelineStage):
    """限速器控制阶段

    不改写query，只检查是否需要限速。
    """

    algo: algo.ReteLimitAlgo

    async def initialize(self, pipeline_config: dict):
        algo_name = 'fixwin'

        algo_class = None

        for algo_cls in algo.preregistered_algos:
            if algo_cls.name == algo_name:
                algo_class = algo_cls
                break
        else:
            raise ValueError(f'未知的限速算法: {algo_name}')

        self.algo = algo_class(self.ap)
        await self.algo.initialize()

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> typing.Union[
        entities.StageProcessResult,
        typing.AsyncGenerator[entities.StageProcessResult, None],
    ]:
        """处理"""
        if stage_inst_name == 'RequireRateLimitOccupancy':
            if await self.algo.require_access(
                query,
                query.launcher_type.value,
                query.launcher_id,
            ):
                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query,
                )
            else:
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    console_notice=f'根据限速规则忽略 {query.launcher_type.value}:{query.launcher_id} 消息',
                    user_notice='请求数超过限速器设定值，已丢弃本消息。',
                )
        elif stage_inst_name == 'ReleaseRateLimitOccupancy':
            await self.algo.release_access(
                query,
                query.launcher_type.value,
                query.launcher_id,
            )
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query,
            )
