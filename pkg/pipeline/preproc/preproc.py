from __future__ import annotations


from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...provider import entities as llm_entities
from ...plugin import events
from ...platform.types import message as platform_message


@stage.stage_class("PreProcessor")
class PreProcessor(stage.PipelineStage):
    """请求预处理阶段

    签出会话、prompt、上文、模型、内容函数。

    改写：
        - session
        - prompt
        - messages
        - user_message
        - use_model
        - use_funcs
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

        query.use_model = conversation.use_model

        query.use_funcs = conversation.use_funcs if query.use_model.tool_call_supported else None


        # 检查vision是否启用，没启用就删除所有图片
        if not self.ap.provider_cfg.data['enable-vision'] or not query.use_model.vision_supported:
            for msg in query.messages:
                if isinstance(msg.content, list):
                    for me in msg.content:
                        if me.type == 'image_url':
                            msg.content.remove(me)

        content_list = []

        for me in query.message_chain:
            if isinstance(me, platform_message.Plain):
                content_list.append(
                    llm_entities.ContentElement.from_text(me.text)
                )
            elif isinstance(me, platform_message.Image):
                if self.ap.provider_cfg.data['enable-vision'] and query.use_model.vision_supported:
                    if me.url is not None:
                        content_list.append(
                            llm_entities.ContentElement.from_image_url(str(me.url))
                        )

        query.user_message = llm_entities.Message(  # TODO 适配多模态输入
            role='user',
            content=content_list
        )
        # =========== 触发事件 PromptPreProcessing

        event_ctx = await self.ap.plugin_mgr.emit_event(
            event=events.PromptPreProcessing(
                session_name=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
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
