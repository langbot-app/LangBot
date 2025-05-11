from __future__ import annotations

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from . import truncator
from .truncators import round


@stage.stage_class("ConversationMessageTruncator")
class ConversationMessageTruncator(stage.PipelineStage):
    """会话消息截断器

    用于截断会话消息链，以适应平台消息长度限制。
    """
    trun: truncator.Truncator

    async def initialize(self):
        use_method = self.ap.pipeline_cfg.data['msg-truncate']['method']

        for trun in truncator.preregistered_truncators:
            if trun.name == use_method:
                self.trun = trun(self.ap)
                break
        else:
            raise ValueError(f"未知的截断器: {use_method}")

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理
        """
        query = await self.trun.truncate(query)

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )