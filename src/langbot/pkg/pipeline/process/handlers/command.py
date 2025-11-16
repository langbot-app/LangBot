from __future__ import annotations
import typing


from .. import handler
from ... import entities
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.events as events


class CommandHandler(handler.MessageHandler):
    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """Process"""

        full_command_text = str(query.message_chain).strip()

        command_text = full_command_text[1:]

        privilege = 1

        if f'{query.launcher_type.value}_{query.launcher_id}' in self.ap.instance_config.data['admins']:
            privilege = 2

        spt = command_text.split(' ')

        event_class = (
            events.PersonCommandSent
            if query.launcher_type == provider_session.LauncherTypes.PERSON
            else events.GroupCommandSent
        )

        event = event_class(
            launcher_type=query.launcher_type.value,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
            command=spt[0],
            params=spt[1:] if len(spt) > 1 else [],
            text_message=full_command_text,
            is_admin=(privilege == 2),
            query=query,
        )

        # Get bound plugins for filtering
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
        event_ctx = await self.ap.plugin_connector.emit_event(event, bound_plugins)

        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is not None:
                mc = event_ctx.event.reply_message_chain

                query.resp_messages.append(mc)

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            else:
                yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)

        else:
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
