from __future__ import annotations
import typing


from .. import handler
from ... import entities
from ....core import entities as core_entities
from ....provider import entities as llm_entities
from ....plugin import events
from ....platform.types import message as platform_message


class CommandHandler(handler.MessageHandler):
    async def handle(
        self,
        query: core_entities.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理"""

        command_text = str(query.message_chain).strip()[1:]

        privilege = 1

        if f'{query.launcher_type.value}_{query.launcher_id}' in self.ap.instance_config.data['admins']:
            privilege = 2

        spt = command_text.split(' ')

        event_class = (
            events.PersonCommandSent
            if query.launcher_type == core_entities.LauncherTypes.PERSON
            else events.GroupCommandSent
        )

        event_ctx = await self.ap.plugin_mgr.emit_event(
            event=event_class(
                launcher_type=query.launcher_type.value,
                launcher_id=query.launcher_id,
                sender_id=query.sender_id,
                command=spt[0],
                params=spt[1:] if len(spt) > 1 else [],
                text_message=str(query.message_chain),
                is_admin=(privilege == 2),
                query=query,
            )
        )

        if event_ctx.is_prevented_default():
            if event_ctx.event.reply is not None:
                mc = platform_message.MessageChain(event_ctx.event.reply)

                query.resp_messages.append(mc)

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            else:
                yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)

        else:
            if event_ctx.event.alter is not None:
                query.message_chain = platform_message.MessageChain([platform_message.Plain(event_ctx.event.alter)])

            session = await self.ap.sess_mgr.get_session(query)

            async for ret in self.ap.cmd_mgr.execute(command_text=command_text, query=query, session=session):
                if ret.error is not None:
                    query.resp_messages.append(
                        llm_entities.Message(
                            role='command',
                            content=str(ret.error),
                        )
                    )

                    self.ap.logger.info(f'命令({query.query_id})报错: {self.cut_str(str(ret.error))}')

                    yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
                elif ret.text is not None or ret.image_url is not None:
                    content: list[llm_entities.ContentElement] = []

                    if ret.text is not None:
                        content.append(llm_entities.ContentElement.from_text(ret.text))

                    if ret.image_url is not None:
                        content.append(llm_entities.ContentElement.from_image_url(ret.image_url))

                    query.resp_messages.append(
                        llm_entities.Message(
                            role='command',
                            content=content,
                        )
                    )

                    self.ap.logger.info(f'命令返回: {self.cut_str(str(content[0]))}')

                    yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
                else:
                    yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
