from __future__ import annotations

from .. import stage, entities
from langbot_plugin.api.entities.builtin.provider import message as provider_message
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from ...utils import importutil
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from . import filters

importutil.import_modules_in_pkg(filters)


@stage.stage_class('PostContentFilterStage')
@stage.stage_class('PreContentFilterStage')
class ContentFilterStage(stage.PipelineStage):
    """Content filter stage

    Runs the content filters of the message policy in effect for the query.

    Pre: checks the incoming message; may rewrite ``message_chain`` or stop.
    Post: checks the reply; may rewrite ``resp_messages[-1].content`` or stop.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    def _result(self, query: pipeline_query.Query, verdict) -> entities.StageProcessResult:
        if verdict.allowed:
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
        return entities.StageProcessResult(
            result_type=entities.ResultType.INTERRUPT,
            new_query=query,
            user_notice=verdict.user_notice,
            console_notice=verdict.console_notice,
        )

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理"""
        policy = await self.ap.message_policy_mgr.for_query(query)
        if stage_inst_name == 'PreContentFilterStage':
            contain_non_text = False

            text_components = [platform_message.Plain, platform_message.Source]

            for me in query.message_chain:
                if type(me) not in text_components:
                    contain_non_text = True
                    break

            if contain_non_text:
                self.ap.logger.debug('消息中包含非文本消息，跳过内容过滤器检查。')
                return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

            verdict = await policy.filter_inbound(query, str(query.message_chain).strip())
            if verdict.allowed and verdict.rewritten:
                query.message_chain = platform_message.MessageChain([platform_message.Plain(text=verdict.text)])
            return self._result(query, verdict)
        elif stage_inst_name == 'PostContentFilterStage':
            # 仅处理 query.resp_messages[-1].content 是 str 的情况
            if isinstance(query.resp_messages[-1], provider_message.Message) and isinstance(
                query.resp_messages[-1].content, str
            ):
                verdict = await policy.filter_outbound(query, query.resp_messages[-1].content)
                if verdict.allowed and verdict.rewritten:
                    query.resp_messages[-1].content = verdict.text
                return self._result(query, verdict)
            else:
                self.ap.logger.debug(
                    'resp_messages[-1] 不是 Message 类型或 query.resp_messages[-1].content 不是 str 类型，跳过内容过滤器检查。'
                )
                return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
        else:
            raise ValueError(f'未知的 stage_inst_name: {stage_inst_name}')
