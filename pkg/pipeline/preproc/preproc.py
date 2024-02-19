from __future__ import annotations

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...provider import entities as llm_entities
from ...plugin import events


@stage.stage_class("PreProcessor")
class PreProcessor(stage.PipelineStage):
    """预处理器
    """

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """处理
        """
        session = await self.ap.sess_mgr.get_session(query)

        conversation = await self.ap.sess_mgr.get_conversation(session)

        # 从会话取出消息和情景预设到query
        query.session = session
        query.prompt = conversation.prompt.copy()
        query.messages = conversation.messages.copy()

        query.user_message = llm_entities.Message(
            role='user',
            content=str(query.message_chain).strip()
        )

        query.use_model = conversation.use_model

        query.use_funcs = conversation.use_funcs

        # =========== 触发事件 PromptPreProcessing
        session = query.session

        event_ctx = await self.ap.plugin_mgr.emit_event(
            event=events.PromptPreProcessing(
                session_name=f'{session.launcher_type.value}_{session.launcher_id}',
                default_prompt=query.prompt.messages,
                prompt=query.messages,
                query=query
            )
        )

        query.prompt.messages = event_ctx.event.default_prompt
        query.messages = event_ctx.event.prompt

        # 根据模型max_tokens剪裁
        max_tokens = min(query.use_model.max_tokens, self.ap.pipeline_cfg.data['submit-messages-tokens'])

        test_messages = query.prompt.messages + query.messages + [query.user_message]

        while await query.use_model.tokenizer.count_token(test_messages, query.use_model) > max_tokens:
            # 前文都pop完了，还是大于max_tokens，由于prompt和user_messages不能删减，报错
            if len(query.prompt.messages) == 0:
                return entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice='输入内容过长，请减少情景预设或者输入内容长度',
                    console_notice='输入内容过长，请减少情景预设或者输入内容长度，或者增大配置文件中的 submit-messages-tokens 项（但不能超过所用模型最大tokens数）'
                )

            query.messages.pop(0) # pop第一个肯定是role=user的
            # 继续pop到第二个role=user前一个
            while len(query.messages) > 0 and query.messages[0].role != 'user':
                query.messages.pop(0)

            test_messages = query.prompt.messages + query.messages + [query.user_message]

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )
