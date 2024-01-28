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
        session = await self.ap.sess_mgr.get_session(query)

        command_text = str(query.message_chain).strip()[1:]

        async for ret in self.ap.cmd_mgr.execute(
            command_text=command_text,
            query=query,
            session=session
        ):
            if ret.error is not None:
                query.resp_message_chain = mirai.MessageChain([
                    mirai.Plain(str(ret.error))
                ])

                yield entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query
                )
            elif ret.text is not None:
                query.resp_message_chain = mirai.MessageChain([
                    mirai.Plain(ret.text)
                ])

                yield entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query
                )
            else:
                yield entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query
                )
