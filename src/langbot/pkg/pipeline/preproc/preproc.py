from __future__ import annotations

import datetime

from .. import stage, entities
from langbot_plugin.api.entities.builtin.provider import message as provider_message
import langbot_plugin.api.entities.events as events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.events as platform_events


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

    @staticmethod
    def _filter_selected_tools(
        tools: list,
        local_agent_config: dict,
    ) -> list:
        if local_agent_config.get('enable-all-tools', True) is not False:
            return tools

        selected_tools = local_agent_config.get('tools', [])
        if not isinstance(selected_tools, list):
            return []

        selected_tool_names = {tool for tool in selected_tools if isinstance(tool, str)}
        return [tool for tool in tools if tool.name in selected_tool_names]

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """Process"""
        selected_runner = query.pipeline_config['ai']['runner']['runner']
        local_agent_config = query.pipeline_config.get('ai', {}).get('local-agent', {})
        include_skill_authoring = (
            selected_runner == 'local-agent' and getattr(self.ap, 'skill_service', None) is not None
        )

        session = await self.ap.sess_mgr.get_session(query)

        # When not local-agent, llm_model is None
        llm_model = None
        if selected_runner == 'local-agent':
            # Read model config — new format is { primary: str, fallbacks: [str] },
            # but handle legacy plain string for backward compatibility
            model_config = local_agent_config.get('model', {})
            if isinstance(model_config, str):
                # Legacy format: plain UUID string
                primary_uuid = model_config
                fallback_uuids = []
            else:
                primary_uuid = model_config.get('primary', '')
                fallback_uuids = model_config.get('fallbacks', [])

            if primary_uuid:
                try:
                    llm_model = await self.ap.model_mgr.get_model_by_uuid(primary_uuid)
                except ValueError:
                    self.ap.logger.warning(f'LLM model {primary_uuid} not found or not configured')

            # Resolve fallback model UUIDs
            if fallback_uuids:
                valid_fallbacks = []
                for fb_uuid in fallback_uuids:
                    try:
                        await self.ap.model_mgr.get_model_by_uuid(fb_uuid)
                        valid_fallbacks.append(fb_uuid)
                    except ValueError:
                        self.ap.logger.warning(f'Fallback model {fb_uuid} not found, skipping')
                if valid_fallbacks:
                    query.variables['_fallback_model_uuids'] = valid_fallbacks

        conversation = await self.ap.sess_mgr.get_conversation(
            query,
            session,
            query.pipeline_config['ai']['local-agent']['prompt'],
            query.pipeline_uuid,
            query.bot_uuid,
        )

        # Expire externally managed conversation ids after the conversation has
        # been idle for longer than the configured conversation expire time.
        # The idle window is measured from the last preprocess/update time, not
        # from the conversation creation time.
        conversation_expire_time = query.pipeline_config.get('ai', {}).get('runner', {}).get('expire-time', None)
        now = datetime.datetime.now()
        if conversation_expire_time is not None and conversation_expire_time > 0:
            last_update_time = getattr(conversation, 'update_time', None) or getattr(conversation, 'create_time', None)
            if last_update_time is not None:
                conversation_idle_time = now.timestamp() - last_update_time.timestamp()
                if conversation_idle_time > conversation_expire_time:
                    self.ap.logger.info(
                        f'Conversation({query.query_id}) is expired (idle: {conversation_idle_time}s), create new conversation'
                    )
                    conversation.uuid = None

        # Treat every preprocess pass as a conversation activity update. This
        # makes future expiry checks use the latest incoming message/preprocess
        # time instead of the first message/creation time.
        conversation.update_time = now

        # 设置query
        query.session = session
        query.prompt = conversation.prompt.copy()
        query.messages = conversation.messages.copy()

        if selected_runner == 'local-agent':
            query.use_funcs = []
            if llm_model:
                query.use_llm_model_uuid = llm_model.model_entity.uuid

                if 'func_call' in (llm_model.model_entity.abilities or []):
                    # Get bound plugins and MCP servers for filtering tools
                    bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
                    bound_mcp_servers = query.variables.get('_pipeline_bound_mcp_servers', None)
                    include_mcp_resource_tools = query.variables.get('_pipeline_mcp_resource_agent_read_enabled', True)
                    all_tools = await self.ap.tool_mgr.get_all_tools(
                        bound_plugins,
                        bound_mcp_servers,
                        include_skill_authoring=include_skill_authoring,
                        include_mcp_resource_tools=include_mcp_resource_tools,
                    )
                    query.use_funcs = self._filter_selected_tools(all_tools, local_agent_config)

                    self.ap.logger.debug(f'Bound plugins: {bound_plugins}')
                    self.ap.logger.debug(f'Bound MCP servers: {bound_mcp_servers}')
                    self.ap.logger.debug(f'Use funcs: {query.use_funcs}')

            # If primary model doesn't support func_call but fallback models exist,
            # load tools anyway since fallback models may support them
            if not query.use_funcs and query.variables.get('_fallback_model_uuids'):
                bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
                bound_mcp_servers = query.variables.get('_pipeline_bound_mcp_servers', None)
                include_mcp_resource_tools = query.variables.get('_pipeline_mcp_resource_agent_read_enabled', True)
                all_tools = await self.ap.tool_mgr.get_all_tools(
                    bound_plugins,
                    bound_mcp_servers,
                    include_skill_authoring=include_skill_authoring,
                    include_mcp_resource_tools=include_mcp_resource_tools,
                )
                query.use_funcs = self._filter_selected_tools(all_tools, local_agent_config)

        sender_name = ''

        if isinstance(query.message_event, platform_events.GroupMessage):
            sender_name = query.message_event.sender.member_name
        elif isinstance(query.message_event, platform_events.FriendMessage):
            sender_name = query.message_event.sender.nickname

        variables = {
            'launcher_type': query.session.launcher_type.value,
            'launcher_id': query.session.launcher_id,
            'sender_id': query.sender_id,
            'session_id': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            'conversation_id': conversation.uuid,
            'msg_create_time': (
                int(query.message_event.time) if query.message_event.time else int(datetime.datetime.now().timestamp())
            ),
            'group_name': query.message_event.group.name
            if isinstance(query.message_event, platform_events.GroupMessage)
            else '',
            'sender_name': sender_name,
        }
        query.variables.update(variables)

        # Check if this model supports vision, if not, remove all images
        # TODO this checking should be performed in runner, and in this stage, the image should be reserved
        if selected_runner == 'local-agent' and llm_model and 'vision' not in (llm_model.model_entity.abilities or []):
            for msg in query.messages:
                if isinstance(msg.content, list):
                    for me in msg.content:
                        if me.type == 'image_url':
                            msg.content.remove(me)

        content_list: list[provider_message.ContentElement] = []

        plain_text = ''
        quote_msg = query.pipeline_config['trigger'].get('misc', '').get('combine-quote-message')

        for me in query.message_chain:
            if isinstance(me, platform_message.Plain):
                content_list.append(provider_message.ContentElement.from_text(me.text))
                plain_text += me.text
            elif isinstance(me, platform_message.Image):
                if selected_runner != 'local-agent' or (
                    llm_model and 'vision' in (llm_model.model_entity.abilities or [])
                ):
                    if me.base64 is not None:
                        content_list.append(provider_message.ContentElement.from_image_base64(me.base64))
            elif isinstance(me, platform_message.Voice):
                # 转成文件链接，让下游 runner 上传到目标模型
                if me.base64:
                    content_list.append(provider_message.ContentElement.from_file_base64(me.base64, 'voice.silk'))
                elif me.url:
                    content_list.append(provider_message.ContentElement.from_file_url(me.url, 'voice'))
            elif isinstance(me, platform_message.File):
                if me.base64:
                    content_list.append(provider_message.ContentElement.from_file_base64(me.base64, me.name))
                elif me.url:
                    content_list.append(provider_message.ContentElement.from_file_url(me.url, me.name))
            elif isinstance(me, platform_message.Quote) and quote_msg:
                for msg in me.origin:
                    if isinstance(msg, platform_message.Plain):
                        content_list.append(provider_message.ContentElement.from_text(msg.text))
                    elif isinstance(msg, platform_message.Image):
                        if selected_runner != 'local-agent' or (
                            llm_model and 'vision' in (llm_model.model_entity.abilities or [])
                        ):
                            if msg.base64 is not None:
                                content_list.append(provider_message.ContentElement.from_image_base64(msg.base64))
                    elif isinstance(msg, platform_message.File):
                        if msg.base64:
                            content_list.append(provider_message.ContentElement.from_file_base64(msg.base64, msg.name))
                        elif msg.url:
                            content_list.append(provider_message.ContentElement.from_file_url(msg.url, msg.name))
                    elif isinstance(msg, platform_message.Voice):
                        if msg.base64:
                            content_list.append(
                                provider_message.ContentElement.from_file_base64(msg.base64, 'voice.silk')
                            )
                        elif msg.url:
                            content_list.append(provider_message.ContentElement.from_file_url(msg.url, 'voice'))

        query.variables['user_message_text'] = plain_text

        query.user_message = provider_message.Message(role='user', content=content_list)

        # Extract knowledge base UUIDs into query variables so plugins can modify them
        # during PromptPreProcessing before the runner performs retrieval.
        kb_uuids = query.pipeline_config['ai']['local-agent'].get('knowledge-bases', [])
        if not kb_uuids:
            old_kb_uuid = query.pipeline_config['ai']['local-agent'].get('knowledge-base', '')
            if old_kb_uuid and old_kb_uuid != '__none__':
                kb_uuids = [old_kb_uuid]
        query.variables['_knowledge_base_uuids'] = list(kb_uuids)

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

        # =========== Skill awareness for the local-agent runner ===========
        # The actual activation goes through the ``activate`` Tool Call so the
        # LLM doesn't see full SKILL.md instructions until it commits to a
        # skill (Claude Code's progressive disclosure). But the LLM still has
        # to KNOW which skills exist to make that choice, so we:
        #   1. resolve the pipeline's bound skills and stash them in
        #      ``query.variables['_pipeline_bound_skills']`` for downstream
        #      visibility checks (skill loader, native exec workdir);
        #   2. inject a short ``Available Skills`` index (name + description
        #      only) into the system prompt. The contributor's original PR
        #      relied on this injection; without it the LLM never discovers
        #      the skills are there and just calls native tools instead.
        if selected_runner == 'local-agent' and self.ap.skill_mgr:
            pipeline_data = await self.ap.pipeline_service.get_pipeline(query.pipeline_uuid)
            extensions_prefs = (pipeline_data or {}).get('extensions_preferences', {})
            enable_all_skills = extensions_prefs.get('enable_all_skills', True)

            if enable_all_skills:
                bound_skills = None  # None = all loaded skills are visible
            else:
                bound_skills = extensions_prefs.get('skills', [])

            query.variables['_pipeline_bound_skills'] = bound_skills

            skill_addition = self.ap.skill_mgr.build_skill_aware_prompt_addition(
                bound_skills=bound_skills,
            )
            if skill_addition:
                # Append to the first system message; create one if the
                # prompt has none. Handles both plain-string and
                # content-element (list) message bodies.
                if query.prompt.messages and query.prompt.messages[0].role == 'system':
                    head = query.prompt.messages[0]
                    if isinstance(head.content, str):
                        head.content = head.content + skill_addition
                    elif isinstance(head.content, list):
                        appended = False
                        for ce in head.content:
                            if getattr(ce, 'type', None) == 'text':
                                ce.text = (ce.text or '') + skill_addition
                                appended = True
                                break
                        if not appended:
                            head.content.append(provider_message.ContentElement(type='text', text=skill_addition))
                else:
                    query.prompt.messages.insert(
                        0,
                        provider_message.Message(role='system', content=skill_addition.strip()),
                    )
                self.ap.logger.debug(
                    f'Skill index injected into system prompt: '
                    f'pipeline={query.pipeline_uuid} '
                    f'bound_skills={bound_skills or "all"} '
                    f'loaded_skills={len(self.ap.skill_mgr.skills)}'
                )
            else:
                self.ap.logger.debug(
                    f'No skills available for prompt injection: '
                    f'pipeline={query.pipeline_uuid} '
                    f'loaded_skills={len(self.ap.skill_mgr.skills)} '
                    f'bound_skills={bound_skills}'
                )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
