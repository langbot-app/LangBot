from __future__ import annotations

import typing

import mirai

from .. import handler
from ... import entities
from ....core import entities as core_entities
from ....provider import entities as llm_entities
from ....plugin import events


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

        # 触发插件事件
        event_class = events.PersonNormalMessageReceived if query.launcher_type == core_entities.LauncherTypes.PERSON else events.GroupNormalMessageReceived

        event_ctx = await self.ap.plugin_mgr.emit_event(
            event=event_class(
                launcher_type=query.launcher_type.value,
                launcher_id=query.launcher_id,
                sender_id=query.sender_id,
                text_message=str(query.message_chain),
                query=query
            )
        )

        if event_ctx.is_prevented_default():
            if event_ctx.event.reply is not None:
                query.resp_message_chain = mirai.MessageChain(event_ctx.event.reply)

                yield entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query
                )
            else:
                yield entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query
                )
        else:

            if event_ctx.event.alter is not None:
                query.message_chain = mirai.MessageChain([
                    mirai.Plain(event_ctx.event.alter)
                ])

            session = await self.ap.sess_mgr.get_session(query)

            conversation = await self.ap.sess_mgr.get_conversation(session)

            # =========== 触发事件 PromptPreProcessing

            event_ctx = await self.ap.plugin_mgr.emit_event(
                event=events.PromptPreProcessing(
                    session_name=f'{session.launcher_type.value}_{session.launcher_id}',
                    default_prompt=conversation.prompt.messages,
                    prompt=conversation.messages,
                    query=query
                )
            )

            conversation.prompt.messages = event_ctx.event.default_prompt
            conversation.messages = event_ctx.event.prompt

            conversation.messages.append(
                llm_entities.Message(
                    role="user",
                    content=str(query.message_chain)
                )
            )

            called_functions = []

            async for result in conversation.use_model.requester.request(query, conversation):
                conversation.messages.append(result)

                # 转换成可读消息
                if result.role == 'assistant':

                    reply_text = ''

                    if result.content is not None:  # 有内容
                        reply_text = result.content

                        # ============= 触发插件事件 ===============
                        event_ctx = await self.ap.plugin_mgr.emit_event(
                            event=events.NormalMessageResponded(
                                launcher_type=query.launcher_type.value,
                                launcher_id=query.launcher_id,
                                sender_id=query.sender_id,
                                session=session,
                                prefix='',
                                response_text=reply_text,
                                finish_reason='stop',
                                funcs_called=called_functions,
                                query=query
                            )
                        )
                        if event_ctx.is_prevented_default():
                            yield entities.StageProcessResult(
                                result_type=entities.ResultType.INTERRUPT,
                                new_query=query
                            )
                        else:
                            if event_ctx.event.reply is not None:
                                
                                query.resp_message_chain = mirai.MessageChain(event_ctx.event.reply)

                            else:

                                query.resp_message_chain = mirai.MessageChain([mirai.Plain(reply_text)])

                            yield entities.StageProcessResult(
                                result_type=entities.ResultType.CONTINUE,
                                new_query=query
                            )

                    if result.tool_calls is not None:  # 有函数调用
                        
                        function_names = [tc.function.name for tc in result.tool_calls]

                        reply_text = f'调用函数 {".".join(function_names)}...'

                        called_functions.extend(function_names)

                        query.resp_message_chain = mirai.MessageChain([mirai.Plain(reply_text)])

                        if self.ap.cfg_mgr.data['trace_function_calls']:
                            
                            event_ctx = await self.ap.plugin_mgr.emit_event(
                                event=events.NormalMessageResponded(
                                    launcher_type=query.launcher_type.value,
                                    launcher_id=query.launcher_id,
                                    sender_id=query.sender_id,
                                    session=session,
                                    prefix='',
                                    response_text=reply_text,
                                    finish_reason='stop',
                                    funcs_called=called_functions,
                                    query=query
                                )
                            )

                            if event_ctx.is_prevented_default():
                                yield entities.StageProcessResult(
                                    result_type=entities.ResultType.INTERRUPT,
                                    new_query=query
                                )
                            else:
                                if event_ctx.event.reply is not None:
                                    
                                    query.resp_message_chain = mirai.MessageChain(event_ctx.event.reply)

                                else:

                                    query.resp_message_chain = mirai.MessageChain([mirai.Plain(reply_text)])

                                yield entities.StageProcessResult(
                                    result_type=entities.ResultType.CONTINUE,
                                    new_query=query
                                )
