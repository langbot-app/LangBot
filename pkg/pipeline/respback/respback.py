from __future__ import annotations

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

        await self.ap.im_mgr.send(
            query.message_event,
            query.resp_message_chain
        )

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )