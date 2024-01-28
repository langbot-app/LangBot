from __future__ import annotations

import typing

import mirai

from .. import handler
from ... import entities
from ....core import entities as core_entities
from ....gai import entities as llm_entities


class ChatMessageHandler(handler.MessageHandler):

    async def handle(
        self,
        query: core_entities.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理
        """
        # 取session
        # 取conversation
        # 调API
        #   生成器
        session = await self.ap.sess_mgr.get_session(query)

        conversation = await self.ap.sess_mgr.get_conversation(session)

        conversation.messages.append(
            llm_entities.Message(
                role="user",
                content=str(query.message_chain)
            )
        )

        async for result in conversation.use_model.requester.request(query, conversation):
            conversation.messages.append(result)

            query.resp_message_chain = mirai.MessageChain([mirai.Plain(str(result))])

            yield entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
