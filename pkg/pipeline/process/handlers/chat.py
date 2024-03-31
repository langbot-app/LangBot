from __future__ import annotations

import typing
import time
import traceback

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
                mc = mirai.MessageChain(event_ctx.event.reply)

                query.resp_messages.append(
                    llm_entities.Message(
                        role='plugin',
                        content=mc,
                    )
                )

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

            if not self.ap.provider_cfg.data['enable-chat']:
                yield entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                )

            if event_ctx.event.alter is not None:
                query.message_chain = mirai.MessageChain([
                    mirai.Plain(event_ctx.event.alter)
                ])

            query.messages.append(
                query.user_message
            )

            text_length = 0

            start_time = time.time()

            try:

                async for result in query.use_model.requester.request(query):
                    query.resp_messages.append(result)

                    self.ap.logger.info(f'对话({query.query_id})响应: {self.cut_str(result.readable_str())}')

                    if result.content is not None:
                        text_length += len(result.content)

                    yield entities.StageProcessResult(
                        result_type=entities.ResultType.CONTINUE,
                        new_query=query
                    )
            except Exception as e:
                
                self.ap.logger.error(f'对话({query.query_id})请求失败: {str(e)}')

                yield entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice='请求失败' if self.ap.platform_cfg.data['hide-exception-info'] else f'{e}',
                    error_notice=f'{e}',
                    debug_notice=traceback.format_exc()
                )
            finally:
                query.session.using_conversation.messages.append(query.user_message)
                query.session.using_conversation.messages.extend(query.resp_messages)

                await self.ap.ctr_mgr.usage.post_query_record(
                    session_type=query.session.launcher_type.value,
                    session_id=str(query.session.launcher_id),
                    query_ability_provider="QChatGPT.Chat",
                    usage=text_length,
                    model_name=query.use_model.name,
                    response_seconds=int(time.time() - start_time),
                    retry_times=-1,
                )