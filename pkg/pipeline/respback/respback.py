from __future__ import annotations

import random
import asyncio

import mirai

from ...core import app

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class("SendResponseBackStage")
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息
    """

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理
        """
        random_delay = random.uniform(*self.ap.platform_cfg.data['force-delay'])

        self.ap.logger.debug(
            "根据规则强制延迟回复: %s s",
            random_delay
        )

        await asyncio.sleep(random_delay)

        await self.ap.platform_mgr.send(
            query.message_event,
            query.resp_message_chain,
            adapter=query.adapter
        )

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )