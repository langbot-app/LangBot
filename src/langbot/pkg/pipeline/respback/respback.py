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

        # Log what we're about to send
        component_types = [type(msg).__name__ for msg in message_chain]
        self.ap.logger.info(
            f'respback: has_chunks={has_chunks}, '
            f'stream_supported={await query.adapter.is_stream_output_supported()}, '
            f'chain_components={component_types}, '
            f'resp_message_chain_count={len(query.resp_message_chain)}'
        )

        try:
            if await query.adapter.is_stream_output_supported() and has_chunks:
                is_final = [msg.is_final for msg in query.resp_messages][0]
                self.ap.logger.info(f'respback: calling reply_message_chunk, is_final={is_final}')
                await query.adapter.reply_message_chunk(
                    message_source=query.message_event,
                    bot_message=query.resp_messages[-1],
                    message=message_chain,
                    quote_origin=quote_origin,
                    is_final=is_final,
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
