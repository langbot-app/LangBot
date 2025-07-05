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
            title='群聊的聊天记录',
            brief='[聊天记录]',
            source='聊天记录',
            preview=['QQ用户: ' + message],
            summary='查看1条转发消息',
        )

        node_list = [
            platform_message.ForwardMessageNode(
                sender_id=query.adapter.bot_account_id,
                sender_name='QQ用户',
                message_chain=platform_message.MessageChain([message]),
            )
        ]

        forward = Forward(display=display, node_list=node_list)

        return [forward]
