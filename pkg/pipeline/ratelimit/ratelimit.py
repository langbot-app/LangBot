from __future__ import annotations

import typing

from .. import entities, stagemgr, stage
from . import algo
from .algos import fixedwin
from ...core import entities as core_entities


@stage.stage_class("RequireRateLimitOccupancy")
@stage.stage_class("ReleaseRateLimitOccupancy")
class RateLimit(stage.PipelineStage):

    algo: algo.ReteLimitAlgo

    async def initialize(self):
        self.algo = fixedwin.FixedWindowAlgo(self.ap)
        await self.algo.initialize()

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str,
    ) -> typing.Union[
        entities.StageProcessResult,
        typing.AsyncGenerator[entities.StageProcessResult, None],
    ]:
        """处理
        """
        if stage_inst_name == "RequireRateLimitOccupancy":
            if await self.algo.require_access(
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
                    console_notice=f"根据限速规则忽略 {query.launcher_type.value}:{query.launcher_id} 消息",
                    user_notice=self.ap.tips_mgr.data['rate_limit_drop_tip']
                )
        elif stage_inst_name == "ReleaseRateLimitOccupancy":
            await self.algo.release_access(
                query.launcher_type,
                query.launcher_id,
            )
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query,
            )
