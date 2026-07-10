from __future__ import annotations

import typing

from .. import entities
from .. import plugin_diagnostics
from .. import stage

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
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

    def _is_final_assistant_message(self, result) -> bool:
        """Whether *result* is the agent's final, tool-call-free answer.

        Intermediate streaming chunks and tool-call rounds must NOT trigger
        outbound attachment collection — only the terminal assistant message.
        """
        if getattr(result, 'role', None) != 'assistant':
            return False
        if result.tool_calls:
            return False
        if isinstance(result, provider_message.MessageChunk):
            return bool(result.is_final)
        return True

    async def _append_outbound_attachments(
        self,
        query: pipeline_query.Query,
        message_chain: platform_message.MessageChain,
    ) -> None:
        """Collect sandbox outbox files and append them to *message_chain*.

        Runs at most once per query (guarded by a query variable) and never
        raises into the pipeline — attachment delivery is best-effort.
        """
        if query.variables.get('_sandbox_outbound_collected'):
            self.ap.logger.info('outbox: already collected for this query, skipping')
            return
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None or not getattr(box_service, 'available', False):
            self.ap.logger.info(
                f'outbox: box_service unavailable (service={box_service is not None}, available={getattr(box_service, "available", False) if box_service else False})'
            )
            return
        query.variables['_sandbox_outbound_collected'] = True
        try:
            attachments = await box_service.collect_outbound_attachments(query)
        except Exception as e:
            self.ap.logger.warning(f'outbox: collection failed: {e}')
            return
        self.ap.logger.info(
            f'outbox: collected {len(attachments)} attachments: {[att.get("type") for att in attachments]}'
        )
        for att in attachments:
            att_type = att.get('type')
            if att_type == 'Image':
                message_chain.append(platform_message.Image(base64=att['base64']))
            elif att_type == 'Voice':
                message_chain.append(platform_message.Voice(base64=att['base64']))
            else:
                message_chain.append(platform_message.File(name=att.get('name', 'file'), base64=att['base64']))

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

                    is_final = self._is_final_assistant_message(result)
                    is_chunk = isinstance(result, provider_message.MessageChunk)
                    self.ap.logger.info(
                        f'wrapper: assistant chunk, content={result.content is not None and len(str(result.content)) > 0}, '
                        f'is_chunk={is_chunk}, is_final={is_final}, tool_calls={len(result.tool_calls) if result.tool_calls else 0}'
                    )

                    if result.content:  # 有内容
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

                            # Attach files the agent produced in the sandbox
                            # outbox, but only on the terminal assistant message.
                            if self._is_final_assistant_message(result):
                                await self._append_outbound_attachments(query, reply_chain)
                                self.ap.logger.info(
                                    f'wrapper: reply_chain has {len(reply_chain)} components after outbox append'
                                )

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
                    elif self._is_final_assistant_message(result):
                        # Final streaming chunk with no text content but
                        # possibly carrying sandbox outbox attachments.
                        self.ap.logger.info('wrapper: final chunk with empty content, collecting outbox')
                        reply_chain = platform_message.MessageChain([])
                        await self._append_outbound_attachments(query, reply_chain)
                        self.ap.logger.info(
                            f'wrapper: reply_chain has {len(reply_chain)} components after outbox (empty content path)'
                        )
                        query.resp_message_chain.append(reply_chain)
                        yield entities.StageProcessResult(
                            result_type=entities.ResultType.CONTINUE,
                            new_query=query,
                        )

                    if result.tool_calls is not None and len(result.tool_calls) > 0:  # 有函数调用
                        function_names = [tc.function.name for tc in result.tool_calls]

                        reply_text = f'Call {".".join(function_names)}...'

                        query.resp_message_chain.append(
                            platform_message.MessageChain([platform_message.Plain(text=reply_text)])
                        )

                        if query.pipeline_config['output']['misc']['track-function-calls']:
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
