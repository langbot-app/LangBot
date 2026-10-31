from __future__ import annotations
import typing

from .. import handler
from ... import entities
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class CommandHandler(handler.MessageHandler):
    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """Process"""

        full_command_text = str(query.message_chain).strip()

        cmd_prefix = ['/']
        if query.bot_uuid and hasattr(self.ap, 'bot_service') and self.ap.bot_service:
            try:
                bot = await self.ap.bot_service.get_bot(
                    query.workspace_uuid,
                    query.bot_uuid,
                    include_secret=False,
                )
                if bot and 'command_settings' in bot and isinstance(bot['command_settings'], dict):
                    cmd_prefix = bot['command_settings'].get('prefixes', ['/'])
            except Exception:
                pass

        matched_prefix = '/'
        sorted_prefixes = sorted(cmd_prefix, key=len, reverse=True)
        for p in sorted_prefixes:
            if p and full_command_text.startswith(p):
                matched_prefix = p
                break

        command_text = full_command_text[len(matched_prefix):].strip()

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
