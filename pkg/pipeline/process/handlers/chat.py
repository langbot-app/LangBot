from __future__ import annotations

import typing
import traceback


from .. import handler
from ... import entities
from ....core import entities as core_entities
from ....provider import runner as runner_module
from ....plugin import events

from ....platform.types import message as platform_message
from ....utils import importutil
from ....provider import runners

importutil.import_modules_in_pkg(runners)


class ChatMessageHandler(handler.MessageHandler):
    async def handle(
        self,
        query: core_entities.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理"""
        # 调API
        #   生成器

        # 触发插件事件
        event_class = (
            events.PersonNormalMessageReceived
            if query.launcher_type == core_entities.LauncherTypes.PERSON
            else events.GroupNormalMessageReceived
        )

        event_ctx = await self.ap.plugin_mgr.emit_event(
            event=event_class(
                launcher_type=query.launcher_type.value,
                launcher_id=query.launcher_id,
                sender_id=query.sender_id,
                text_message=str(query.message_chain),
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
                # if isinstance(event_ctx.event, str):  # 现在暂时不考虑多模态alter
                query.user_message.content = event_ctx.event.alter

            text_length = 0

            try:
                for r in runner_module.preregistered_runners:
                    if r.name == query.pipeline_config['ai']['runner']['runner']:
                        runner = r(self.ap, query.pipeline_config)
                        break
                else:
                    raise ValueError(f'未找到请求运行器: {query.pipeline_config["ai"]["runner"]["runner"]}')

                async for result in runner.run(query):
                    query.resp_messages.append(result)

                    self.ap.logger.info(f'对话({query.query_id})响应: {self.cut_str(result.readable_str())}')

                    if result.content is not None:
                        text_length += len(result.content)

                    yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

                query.session.using_conversation.messages.append(query.user_message)
                query.session.using_conversation.messages.extend(query.resp_messages)
            except Exception as e:
                self.ap.logger.error(f'对话({query.query_id})请求失败: {type(e).__name__} {str(e)}')

                hide_exception_info = query.pipeline_config['output']['misc']['hide-exception']

                yield entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice='请求失败' if hide_exception_info else f'{e}',
                    error_notice=f'{e}',
                    debug_notice=traceback.format_exc(),
                )
            finally:
                # TODO statistics
                pass
