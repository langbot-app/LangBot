from __future__ import annotations

import random
import asyncio


from ...platform.types import events as platform_events
from ...platform.types import message as platform_message

from .. import stage, entities
from ...core import entities as core_entities


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息"""

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理"""

        random_range = (
            query.pipeline_config['output']['force-delay']['min'],
            query.pipeline_config['output']['force-delay']['max'],
        )

        random_delay = random.uniform(*random_range)

        self.ap.logger.debug('根据规则强制延迟回复: %s s', random_delay)

        await asyncio.sleep(random_delay)

        if query.pipeline_config['output']['misc']['at-sender'] and isinstance(
            query.message_event, platform_events.GroupMessage
        ):
            query.resp_message_chain[-1].insert(0, platform_message.At(query.message_event.sender.id))

        quote_origin = query.pipeline_config['output']['misc']['quote-origin']

        await query.adapter.reply_message(
            message_source=query.message_event,
            message=query.resp_message_chain[-1],
            quote_origin=quote_origin,
        )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
