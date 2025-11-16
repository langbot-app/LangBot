from __future__ import annotations

import uuid
import typing
import traceback


from .. import handler
from ... import entities
from ....provider import runner as runner_module

import langbot_plugin.api.entities.events as events
from ....utils import importutil
from ....provider import runners
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


importutil.import_modules_in_pkg(runners)


class ChatMessageHandler(handler.MessageHandler):
    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理"""
        # 调API
        #   生成器

        # 触发插件事件
        event_class = (
            events.PersonNormalMessageReceived
            if query.launcher_type == provider_session.LauncherTypes.PERSON
            else events.GroupNormalMessageReceived
        )

        event = event_class(
            launcher_type=query.launcher_type.value,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
            text_message=str(query.message_chain),
            query=query,
        )

        # Get bound plugins for filtering
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
        event_ctx = await self.ap.plugin_connector.emit_event(event, bound_plugins)

        is_create_card = False  # 判断下是否需要创建流式卡片

        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is not None:
                mc = event_ctx.event.reply_message_chain
                query.resp_messages.append(mc)

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            else:
                yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
        else:
            if event_ctx.event.user_message_alter is not None:
                # if isinstance(event_ctx.event, str):  # 现在暂时不考虑多模态alter
                query.user_message.content = event_ctx.event.user_message_alter

            text_length = 0
            try:
                is_stream = await query.adapter.is_stream_output_supported()
            except AttributeError:
                is_stream = False

            try:
                for r in runner_module.preregistered_runners:
                    if r.name == query.pipeline_config['ai']['runner']['runner']:
                        runner = r(self.ap, query.pipeline_config)
                        break
                else:
                    raise ValueError(f'未找到请求运行器: {query.pipeline_config["ai"]["runner"]["runner"]}')
                if is_stream:
                    resp_message_id = uuid.uuid4()

                    async for result in runner.run(query):
                        result.resp_message_id = str(resp_message_id)
                        if query.resp_messages:
                            query.resp_messages.pop()
                        if query.resp_message_chain:
                            query.resp_message_chain.pop()
                        # 此时连接外部 AI 服务正常,创建卡片
                        if not is_create_card:  # 只有不是第一次才创建卡片
                            await query.adapter.create_message_card(str(resp_message_id), query.message_event)
                            is_create_card = True
                        query.resp_messages.append(result)
                        self.ap.logger.info(f'对话({query.query_id})流式响应: {self.cut_str(result.readable_str())}')

                        if result.content is not None:
                            text_length += len(result.content)

                        yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

                else:
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
                traceback.print_exc()

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
