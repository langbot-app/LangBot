from __future__ import annotations

import random
import asyncio
import hashlib


import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from .. import stage, entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


def _summarize_stream_text(content: str, tail_length: int = 32) -> dict[str, str | int]:
    text = content or ''
    encoded = text.encode('utf-8')
    return {
        'chars': len(text),
        'bytes': len(encoded),
        'tail_repr': repr(text[-tail_length:]),
        'md5': hashlib.md5(encoded).hexdigest()[:12] if encoded else '0' * 12,
    }


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """发送响应消息"""

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理"""

        has_chunks = any(isinstance(msg, provider_message.MessageChunk) for msg in query.resp_messages)
        is_stream_mode = await query.adapter.is_stream_output_supported() and has_chunks

        # 流式模式下跳过强制延迟，确保首字快速响应
        if not is_stream_mode:
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

        # TODO 命令与流式的兼容性问题
        if is_stream_mode:
            latest_chunk = next(
                (msg for msg in reversed(query.resp_messages) if isinstance(msg, provider_message.MessageChunk)),
                None,
            )
            stream_text = str(query.resp_message_chain[-1])
            summary = _summarize_stream_text(stream_text)
            self.ap.logger.debug(
                '[wecom-stream] '
                f'action=respback_reply_chunk '
                f'query_id={query.query_id or "-"} '
                f'resp_message_id={getattr(latest_chunk, "resp_message_id", "") or "-"} '
                f'finish={str(latest_chunk.is_final if latest_chunk else False).lower()} '
                f'content_chars={summary["chars"]} '
                f'content_bytes={summary["bytes"]} '
                f'content_tail={summary["tail_repr"]} '
                f'content_md5={summary["md5"]}'
            )
            await query.adapter.reply_message_chunk(
                message_source=query.message_event,
                bot_message=query.resp_messages[-1],
                message=query.resp_message_chain[-1],
                quote_origin=quote_origin,
                is_final=latest_chunk.is_final if latest_chunk else False,
            )
        else:
            await query.adapter.reply_message(
                message_source=query.message_event,
                message=query.resp_message_chain[-1],
                quote_origin=quote_origin,
            )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
