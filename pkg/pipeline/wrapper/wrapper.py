from __future__ import annotations

import typing

import mirai

from ...core import app, entities as core_entities
from .. import entities
from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr
from ...plugin import events


@stage.stage_class("ResponseWrapper")
class ResponseWrapper(stage.PipelineStage):

    async def initialize(self):
        pass

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理
        """
        
        if query.resp_messages[-1].role == 'command':
            query.resp_message_chain = mirai.MessageChain("[bot] "+query.resp_messages[-1].content)

            yield entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
        elif query.resp_messages[-1].role == 'plugin':
            if not isinstance(query.resp_messages[-1].content, mirai.MessageChain):
                query.resp_message_chain = mirai.MessageChain(query.resp_messages[-1].content)
            else:
                query.resp_message_chain = query.resp_messages[-1].content

            yield entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
        else:

            if query.resp_messages[-1].role == 'assistant':
                result = query.resp_messages[-1]
                session = await self.ap.sess_mgr.get_session(query)

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
                            funcs_called=[fc.function.name for fc in result.tool_calls] if result.tool_calls is not None else [],
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

                    query.resp_message_chain = mirai.MessageChain([mirai.Plain(reply_text)])

                    if self.ap.platform_cfg.data['track-function-calls']:
                        
                        event_ctx = await self.ap.plugin_mgr.emit_event(
                            event=events.NormalMessageResponded(
                                launcher_type=query.launcher_type.value,
                                launcher_id=query.launcher_id,
                                sender_id=query.sender_id,
                                session=session,
                                prefix='',
                                response_text=reply_text,
                                finish_reason='stop',
                                funcs_called=[fc.function.name for fc in result.tool_calls] if result.tool_calls is not None else [],
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