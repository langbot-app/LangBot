from __future__ import annotations

import datetime

from .. import stage, entities
from langbot_plugin.api.entities.builtin.provider import message as provider_message
import langbot_plugin.api.entities.events as events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


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
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """Process"""
        selected_runner = query.pipeline_config['ai']['runner']['runner']

        session = await self.ap.sess_mgr.get_session(query)

        # When not local-agent, llm_model is None
        try:
            llm_model = (
                await self.ap.model_mgr.get_model_by_uuid(query.pipeline_config['ai']['local-agent']['model'])
                if selected_runner == 'local-agent'
                else None
            )
        except ValueError:
            self.ap.logger.warning(
                f'LLM model {query.pipeline_config["ai"]["local-agent"]["model"] + " "}not found or not configured'
            )
            llm_model = None

        conversation = await self.ap.sess_mgr.get_conversation(
            query,
            session,
            query.pipeline_config['ai']['local-agent']['prompt'],
            query.pipeline_uuid,
            query.bot_uuid,
        )

        # 设置query
        query.session = session
        query.prompt = conversation.prompt.copy()
        query.messages = conversation.messages.copy()

        if selected_runner == 'local-agent' and llm_model:
            query.use_funcs = []
            query.use_llm_model_uuid = llm_model.model_entity.uuid

            if llm_model.model_entity.abilities.__contains__('func_call'):
                # Get bound plugins and MCP servers for filtering tools
                bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
                bound_mcp_servers = query.variables.get('_pipeline_bound_mcp_servers', None)
                query.use_funcs = await self.ap.tool_mgr.get_all_tools(bound_plugins, bound_mcp_servers)

                self.ap.logger.debug(f'Bound plugins: {bound_plugins}')
                self.ap.logger.debug(f'Bound MCP servers: {bound_mcp_servers}')
                self.ap.logger.debug(f'Use funcs: {query.use_funcs}')

        variables = {
            'session_id': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            'conversation_id': conversation.uuid,
            'msg_create_time': (
                int(query.message_event.time) if query.message_event.time else int(datetime.datetime.now().timestamp())
            ),
        }
        query.variables.update(variables)

        # Check if this model supports vision, if not, remove all images
        # TODO this checking should be performed in runner, and in this stage, the image should be reserved
        if (
            selected_runner == 'local-agent'
            and llm_model
            and not llm_model.model_entity.abilities.__contains__('vision')
        ):
            for msg in query.messages:
                if isinstance(msg.content, list):
                    for me in msg.content:
                        if me.type == 'image_url':
                            msg.content.remove(me)

        content_list: list[provider_message.ContentElement] = []

        plain_text = ''
        qoute_msg = query.pipeline_config['trigger'].get('misc', '').get('combine-quote-message')

        for me in query.message_chain:
            if isinstance(me, platform_message.Plain):
                content_list.append(provider_message.ContentElement.from_text(me.text))
                plain_text += me.text
            elif isinstance(me, platform_message.Image):
                if selected_runner != 'local-agent' or (
                    llm_model and llm_model.model_entity.abilities.__contains__('vision')
                ):
                    if me.base64 is not None:
                        content_list.append(provider_message.ContentElement.from_image_base64(me.base64))
            elif isinstance(me, platform_message.File):
                # if me.url is not None:
                content_list.append(provider_message.ContentElement.from_file_url(me.url, me.name))
            elif isinstance(me, platform_message.Quote) and qoute_msg:
                for msg in me.origin:
                    if isinstance(msg, platform_message.Plain):
                        content_list.append(provider_message.ContentElement.from_text(msg.text))
                    elif isinstance(msg, platform_message.Image):
                        if selected_runner != 'local-agent' or (
                            llm_model and llm_model.model_entity.abilities.__contains__('vision')
                        ):
                            if msg.base64 is not None:
                                content_list.append(provider_message.ContentElement.from_image_base64(msg.base64))

        query.variables['user_message_text'] = plain_text

        query.user_message = provider_message.Message(role='user', content=content_list)
        # =========== 触发事件 PromptPreProcessing

        event = events.PromptPreProcessing(
            session_name=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            default_prompt=query.prompt.messages,
            prompt=query.messages,
            query=query,
        )

        # Get bound plugins for filtering
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
        event_ctx = await self.ap.plugin_connector.emit_event(event, bound_plugins)

        query.prompt.messages = event_ctx.event.default_prompt
        query.messages = event_ctx.event.prompt

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
