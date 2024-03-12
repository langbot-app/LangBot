from __future__ import annotations

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...provider import entities as llm_entities
from ...plugin import events


@stage.stage_class("PreProcessor")
class PreProcessor(stage.PipelineStage):
    """请求预处理阶段
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

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )
