# 转发消息组件
from __future__ import annotations


from .. import strategy as strategy_model

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message

ForwardMessageDiaplay = platform_message.ForwardMessageDiaplay
Forward = platform_message.Forward


@strategy_model.strategy_class('forward')
class ForwardComponentStrategy(strategy_model.LongTextStrategy):
    async def process(self, message: str, query: pipeline_query.Query) -> list[platform_message.MessageComponent]:
        display = ForwardMessageDiaplay(
            title='Group chat history',
            brief='[Chat history]',
            source='Chat history',
            preview=['User: ' + message],
            summary='View 1 forwarded message',
        )

        node_list = [
            platform_message.ForwardMessageNode(
                sender_id=query.adapter.bot_account_id,
                sender_name='User',
                message_chain=platform_message.MessageChain([platform_message.Plain(text=message)]),
            )
        ]

        forward = Forward(display=display, node_list=node_list)

        return [forward]
