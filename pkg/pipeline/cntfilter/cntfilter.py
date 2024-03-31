from __future__ import annotations

import mirai

from ...core import app

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr
from . import filter as filter_model, entities as filter_entities
from .filters import cntignore, banwords, baiduexamine


@stage.stage_class('PostContentFilterStage')
@stage.stage_class('PreContentFilterStage')
class ContentFilterStage(stage.PipelineStage):
    """内容过滤阶段"""

    filter_chain: list[filter_model.ContentFilter]

    def __init__(self, ap: app.Application):
        self.filter_chain = []
        super().__init__(ap)

    async def initialize(self):

        filters_required = [
            "content-ignore",
        ]

        if self.ap.pipeline_cfg.data['check-sensitive-words']:
            filters_required.append("ban-word-filter")

        if self.ap.pipeline_cfg.data['baidu-cloud-examine']['enable']:
            filters_required.append("baidu-cloud-examine")

        for filter in filter_model.preregistered_filters:
            if filter.name in filters_required:
                self.filter_chain.append(
                    filter(self.ap)
                )

        for filter in self.filter_chain:
            await filter.initialize()

    async def _pre_process(
        self,
        message: str,
        query: core_entities.Query,
    ) -> entities.StageProcessResult:
        """请求llm前处理消息
        只要有一个不通过就不放行，只放行 PASS 的消息
        """
        if not self.ap.pipeline_cfg.data['income-msg-check']:
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
        else:
            for filter in self.filter_chain:
                if filter_entities.EnableStage.PRE in filter.enable_stages:
                    result = await filter.process(message)

                    if result.level in [
                        filter_entities.ResultLevel.BLOCK,
                        filter_entities.ResultLevel.MASKED
                    ]:
                        return entities.StageProcessResult(
                            result_type=entities.ResultType.INTERRUPT,
                            new_query=query,
                            user_notice=result.user_notice,
                            console_notice=result.console_notice
                        )
                    elif result.level == filter_entities.ResultLevel.PASS:  # 传到下一个
                        message = result.replacement
            
            query.message_chain = mirai.MessageChain(
                mirai.Plain(message)
            )

            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
        
    async def _post_process(
        self,
        message: str,
        query: core_entities.Query,
    ) -> entities.StageProcessResult:
        """请求llm后处理响应
        只要是 PASS 或者 MASKED 的就通过此 filter，将其 replacement 设置为message，进入下一个 filter
        """
        if message is None:
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
        else:
            message = message.strip()
            for filter in self.filter_chain:
                if filter_entities.EnableStage.POST in filter.enable_stages:
                    result = await filter.process(message)

                    if result.level == filter_entities.ResultLevel.BLOCK:
                        return entities.StageProcessResult(
                            result_type=entities.ResultType.INTERRUPT,
                            new_query=query,
                            user_notice=result.user_notice,
                            console_notice=result.console_notice
                        )
                    elif result.level in [
                        filter_entities.ResultLevel.PASS,
                        filter_entities.ResultLevel.MASKED
                    ]:
                        message = result.replacement

            query.resp_messages[-1].content = message

            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str
    ) -> entities.StageProcessResult:
        """处理
        """
        if stage_inst_name == 'PreContentFilterStage':
            return await self._pre_process(
                str(query.message_chain).strip(),
                query
            )
        elif stage_inst_name == 'PostContentFilterStage':
            # 仅处理 query.resp_messages[-1].content 是 str 的情况
            if isinstance(query.resp_messages[-1].content, str):
                return await self._post_process(
                    query.resp_messages[-1].content,
                    query
                )
            else:
                self.ap.logger.debug(f"resp_messages[-1] 不是 str 类型，跳过内容过滤器检查。")
                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query
                )
        else:
            raise ValueError(f'未知的 stage_inst_name: {stage_inst_name}')
