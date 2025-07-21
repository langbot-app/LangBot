from __future__ import annotations

import datetime

from .. import stage, entities
from ...core import entities as core_entities
from ...provider import entities as llm_entities
from ...plugin import events
from ...platform.types import message as platform_message


@stage.stage_class('PreProcessor')
class PreProcessor(stage.PipelineStage):
    """Request pre-processing stage

    Check out session, prompt, context, model, and content functions.

    Rewrite:
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
        """Process"""
        selected_runner = query.pipeline_config['ai']['runner']['runner']

        session = await self.ap.sess_mgr.get_session(query)

        # When not local-agent, llm_model is None
        llm_model = (
            await self.ap.model_mgr.get_model_by_uuid(query.pipeline_config['ai']['local-agent']['model'])
            if selected_runner == 'local-agent'
            else None
        )

        conversation = await self.ap.sess_mgr.get_conversation(
            query,
            session,
            query.pipeline_config['ai']['local-agent']['prompt'],
            query.pipeline_uuid,
            query.bot_uuid,
        )

        conversation.use_llm_model = llm_model

        # Set query
        query.session = session
        query.prompt = conversation.prompt.copy()
        query.messages = conversation.messages.copy()

        query.use_llm_model = llm_model

        if selected_runner == 'local-agent':
            query.use_funcs = (
                conversation.use_funcs if query.use_llm_model.model_entity.abilities.__contains__('func_call') else None
            )

        query.variables = {
            'session_id': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            'conversation_id': conversation.uuid,
            'msg_create_time': (
                int(query.message_event.time) if query.message_event.time else int(datetime.datetime.now().timestamp())
            ),
        }

        # Check if this model supports vision, if not, remove all images
        # TODO this checking should be performed in runner, and in this stage, the image should be reserved
        if selected_runner == 'local-agent' and not query.use_llm_model.model_entity.abilities.__contains__('vision'):
            for msg in query.messages:
                if isinstance(msg.content, list):
                    for me in msg.content:
                        if me.type == 'image_url':
                            msg.content.remove(me)

        content_list: list[llm_entities.ContentElement] = []

        plain_text = ''
        qoute_msg = query.pipeline_config['trigger'].get('misc', '').get('combine-quote-message')

        # tidy the content_list
        # combine all text content into one, and put it in the first position
        for me in query.message_chain:
            if isinstance(me, platform_message.Plain):
                plain_text += me.text
            elif isinstance(me, platform_message.Image):
                if selected_runner != 'local-agent' or query.use_llm_model.model_entity.abilities.__contains__(
                    'vision'
                ):
                    if me.base64 is not None:
                        content_list.append(llm_entities.ContentElement.from_image_base64(me.base64))
            elif isinstance(me, platform_message.Quote) and qoute_msg:
                for msg in me.origin:
                    if isinstance(msg, platform_message.Plain):
                        content_list.append(llm_entities.ContentElement.from_text(msg.text))
                    elif isinstance(msg, platform_message.Image):
                        if selected_runner != 'local-agent' or query.use_llm_model.model_entity.abilities.__contains__(
                            'vision'
                        ):
                            if msg.base64 is not None:
                                content_list.append(llm_entities.ContentElement.from_image_base64(msg.base64))

        content_list.insert(0, llm_entities.ContentElement.from_text(plain_text))

        query.variables['user_message_text'] = plain_text

        query.user_message = llm_entities.Message(role='user', content=content_list)
        # =========== Trigger event PromptPreProcessing

        event_ctx = await self.ap.plugin_mgr.emit_event(
            event=events.PromptPreProcessing(
                session_name=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                default_prompt=query.prompt.messages,
                prompt=query.messages,
                query=query,
            )
        )

        query.prompt.messages = event_ctx.event.default_prompt
        query.messages = event_ctx.event.prompt

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
