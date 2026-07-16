from __future__ import annotations

import random
import asyncio


import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from .. import stage, entities
from .. import plugin_diagnostics
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息"""

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
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
            query.resp_message_chain[-1].insert(0, platform_message.At(target=query.message_event.sender.id))

        quote_origin = query.pipeline_config['output']['misc']['quote-origin']

        has_chunks = any(isinstance(msg, provider_message.MessageChunk) for msg in query.resp_messages)
        # TODO 命令与流式的兼容性问题
        response_index = len(query.resp_message_chain) - 1
        message_chain = query.resp_message_chain[-1]

        try:
            if await query.adapter.is_stream_output_supported() and has_chunks:
                is_final = [msg.is_final for msg in query.resp_messages][-1]
                bot_msg = query.resp_messages[-1]
                # Read the keep_stream hint that the runner may have set on
                # the MessageChunk's provider_specific_fields.  This tells
                # adapters (e.g. WeComBot WS) to keep the stream session
                # alive across multi-round tool-call loops.
                keep_stream = False
                psf = getattr(bot_msg, 'provider_specific_fields', None)
                if psf:
                    keep_stream = bool(psf.get('keep_stream', False))
                await query.adapter.reply_message_chunk(
                    message_source=query.message_event,
                    bot_message=bot_msg,
                    message=message_chain,
                    quote_origin=quote_origin,
                    is_final=is_final,
                    keep_stream=keep_stream,
                )
            else:
                await query.adapter.reply_message(
                    message_source=query.message_event,
                    message=message_chain,
                    quote_origin=quote_origin,
                )
        except Exception as e:
            await plugin_diagnostics.notify_response_delivery_failure(
                self.ap,
                query,
                response_index,
                message_chain,
                e,
            )
            plugin_diagnostics.clear_response_source(query, response_index)
            raise
        plugin_diagnostics.clear_response_source(query, response_index)

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
