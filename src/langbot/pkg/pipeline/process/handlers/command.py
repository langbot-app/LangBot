from __future__ import annotations
import typing

from .. import handler
from ... import entities
from ...command_text import command_text_from_chain, strip_command_prefix
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class CommandHandler(handler.MessageHandler):
    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """Process"""

        full_command_text = command_text_from_chain(query.message_chain)

        from ..command_settings import get_bot_command_settings

        _, cmd_prefix = await get_bot_command_settings(self.ap, query)
        command_text = strip_command_prefix(full_command_text, sorted(cmd_prefix, key=len, reverse=True))

        session = await self.ap.sess_mgr.get_session(query)

        async for ret in self.ap.cmd_mgr.execute(
            command_text=command_text, full_command_text=full_command_text, query=query, session=session
        ):
            if ret.error is not None:
                query.resp_messages.append(
                    provider_message.Message(
                        role='command',
                        content=str(ret.error),
                    )
                )

                self.ap.logger.info(f'Command({query.query_id}) error: {self.cut_str(str(ret.error))}')

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            elif (
                ret.text is not None
                or ret.image_url is not None
                or ret.image_base64 is not None
                or ret.file_url is not None
            ):
                content: list[provider_message.ContentElement] = []

                if ret.text is not None:
                    content.append(provider_message.ContentElement.from_text(ret.text))

                if ret.image_url is not None:
                    content.append(provider_message.ContentElement.from_image_url(ret.image_url))

                if ret.image_base64 is not None:
                    content.append(provider_message.ContentElement.from_image_base64(ret.image_base64))

                if ret.file_url is not None:
                    # 此时为 file 类型
                    content.append(provider_message.ContentElement.from_file_url(ret.file_url, ret.file_name))
                query.resp_messages.append(
                    provider_message.Message(
                        role='command',
                        content=content,
                    )
                )

                self.ap.logger.info(f'Command returned: {self.cut_str(str(content[0]))}')

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            else:
                yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
