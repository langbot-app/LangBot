from __future__ import annotations

from ...i18n import pipeline_notice

import typing

from .. import entities, stage
from ...utils import importutil

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from . import algos

importutil.import_modules_in_pkg(algos)


@stage.stage_class('RequireRateLimitOccupancy')
@stage.stage_class('ReleaseRateLimitOccupancy')
class RateLimit(stage.PipelineStage):
    """Rate limit stage

    Takes and releases a slot in the rate limit of the message policy in
    effect for the query. Does not rewrite the query.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> typing.Union[
        entities.StageProcessResult,
        typing.AsyncGenerator[entities.StageProcessResult, None],
    ]:
        """处理"""
        policy = await self.ap.message_policy_mgr.for_query(query)
        if stage_inst_name == 'RequireRateLimitOccupancy':
            if await policy.acquire_rate_limit(query):
                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query,
                )
            else:
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    console_notice=f'根据限速规则忽略 {query.launcher_type.value}:{query.launcher_id} 消息',
                    user_notice=pipeline_notice(query, 'rate-limit-hint', 'Too many requests. Please try again later.'),
                )
        elif stage_inst_name == 'ReleaseRateLimitOccupancy':
            await policy.release_rate_limit(query)
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query,
            )
