from __future__ import annotations

from ...i18n import pipeline_notice

import typing

from .. import entities
from .. import plugin_diagnostics
from .. import stage

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.events as events


@stage.stage_class('ResponseWrapper')
class ResponseWrapper(stage.PipelineStage):
    """回复包装阶段

    把回复的 message 包装成人类识读的形式。

    改写：
        - resp_message_chain
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """处理"""

        # 如果 resp_messages[-1] 已经是 MessageChain 了
        if isinstance(query.resp_messages[-1], platform_message.MessageChain):
            query.resp_message_chain.append(query.resp_messages[-1])
            plugin_diagnostics.consume_pending_plugin_response_source(
                query,
                query.resp_messages[-1],
                len(query.resp_message_chain) - 1,
            )

            yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        else:
            if query.resp_messages[-1].role == 'command':
                query.resp_message_chain.append(
                    query.resp_messages[-1].get_content_platform_message_chain(prefix_text='[bot] ')
                )

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            elif query.resp_messages[-1].role == 'plugin':
                query.resp_message_chain.append(query.resp_messages[-1].get_content_platform_message_chain())

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            else:
                if query.resp_messages[-1].role == 'assistant':
                    result = query.resp_messages[-1]
                    session = await self.ap.sess_mgr.get_session(query)

                    reply_text = ''

                    if result.content or getattr(result, 'attachments', None):
                        reply_text = str(result.get_content_platform_message_chain())

                        # ============= 触发插件事件 ===============
                        event = events.NormalMessageResponded(
                            launcher_type=query.launcher_type.value,
                            launcher_id=query.launcher_id,
                            sender_id=query.sender_id,
                            session=session,
                            prefix='',
                            response_text=reply_text,
                            finish_reason='stop',
                            funcs_called=[fc.function.name for fc in result.tool_calls]
                            if result.tool_calls is not None
                            else [],
                            query=query,
                        )

                        # Get bound plugins for filtering
                        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
                        event_ctx = await self.ap.plugin_connector.emit_event(event, bound_plugins)

                        if event_ctx.is_prevented_default():
                            yield entities.StageProcessResult(
                                result_type=entities.ResultType.INTERRUPT,
                                new_query=query,
                            )
                        else:
                            if event_ctx.event.reply_message_chain is not None:
                                reply_chain = event_ctx.event.reply_message_chain
                                is_plugin_reply = True
                            else:
                                reply_chain = result.get_content_platform_message_chain()
                                is_plugin_reply = False

                            query.resp_message_chain.append(reply_chain)
                            if is_plugin_reply:
                                plugin_diagnostics.record_last_plugin_response_source(
                                    query,
                                    plugin_diagnostics.get_response_sources(event_ctx),
                                    plugin_diagnostics.get_emitted_plugins(event_ctx),
                                    event.event_name,
                                )

                            yield entities.StageProcessResult(
                                result_type=entities.ResultType.CONTINUE,
                                new_query=query,
                            )
                    if result.tool_calls is not None and len(result.tool_calls) > 0:  # 有函数调用
                        function_names = [tc.function.name for tc in result.tool_calls]

                        reply_text = pipeline_notice(
                            query, 'tool-call-hint', 'Calling {tools}...', tools=', '.join(function_names)
                        )

                        # Only surface the tool-call notice when the pipeline option
                        # is enabled. Emitting it unconditionally would become the
                        # final streaming chunk, closing the stream early and pushing
                        # the real answer into a separate message.
                        if query.pipeline_config['output']['misc']['track-function-calls']:
                            query.resp_message_chain.append(
                                platform_message.MessageChain([platform_message.Plain(text=reply_text)])
                            )

                            event = events.NormalMessageResponded(
                                launcher_type=query.launcher_type.value,
                                launcher_id=query.launcher_id,
                                sender_id=query.sender_id,
                                session=session,
                                prefix='',
                                response_text=reply_text,
                                finish_reason='stop',
                                funcs_called=[fc.function.name for fc in result.tool_calls]
                                if result.tool_calls is not None
                                else [],
                                query=query,
                            )

                            # Get bound plugins for filtering
                            bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
                            event_ctx = await self.ap.plugin_connector.emit_event(event, bound_plugins)

                            if event_ctx.is_prevented_default():
                                yield entities.StageProcessResult(
                                    result_type=entities.ResultType.INTERRUPT,
                                    new_query=query,
                                )
                            else:
                                if event_ctx.event.reply_message_chain is not None:
                                    query.resp_message_chain.append(event_ctx.event.reply_message_chain)
                                    plugin_diagnostics.record_last_plugin_response_source(
                                        query,
                                        plugin_diagnostics.get_response_sources(event_ctx),
                                        plugin_diagnostics.get_emitted_plugins(event_ctx),
                                        event.event_name,
                                    )

                                else:
                                    query.resp_message_chain.append(
                                        platform_message.MessageChain([platform_message.Plain(text=reply_text)])
                                    )

                                yield entities.StageProcessResult(
                                    result_type=entities.ResultType.CONTINUE,
                                    new_query=query,
                                )
