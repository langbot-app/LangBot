from __future__ import annotations
import typing

import mirai

from .. import handler
from ... import entities
from ....core import entities as core_entities


class CommandHandler(handler.MessageHandler):

    async def handle(
        self,
        query: core_entities.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理
        """
        query.resp_message_chain = mirai.MessageChain([
            mirai.Plain('CommandHandler')
        ])

        yield entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )

        query.resp_message_chain = mirai.MessageChain([
            mirai.Plain('The Second Message')
        ])

        yield entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )