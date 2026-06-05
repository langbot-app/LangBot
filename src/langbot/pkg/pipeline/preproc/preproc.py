from __future__ import annotations

import datetime
import typing

from .. import stage, entities
from langbot_plugin.api.entities.builtin.provider import message as provider_message
import langbot_plugin.api.entities.events as events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.events as platform_events

from ...agent.runner.descriptor import AgentRunnerDescriptor
from ...agent.runner.config_migration import ConfigMigration
from ...agent.runner import config_schema


DEFAULT_PROMPT_CONFIG = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
]


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

    async def _get_runner_descriptor(
        self,
        runner_id: str | None,
        bound_plugins: list[str] | None,
    ) -> AgentRunnerDescriptor | None:
        if not runner_id:
            return None

        registry = getattr(self.ap, 'agent_runner_registry', None)
        if registry is None:
            return None

        try:
            return await registry.get(runner_id, bound_plugins)
        except Exception as e:
            self.ap.logger.debug(f'Unable to load AgentRunner descriptor for {runner_id}: {e}')
            return None

    async def _resolve_llm_model(
        self,
        primary_uuid: str,
    ) -> typing.Any | None:
        if primary_uuid in config_schema.NONE_SENTINELS:
            return None
        try:
            return await self.ap.model_mgr.get_model_by_uuid(primary_uuid)
        except ValueError:
            self.ap.logger.warning(f'LLM model {primary_uuid} not found or not configured')
            return None

    async def _resolve_fallback_models(self, fallback_uuids: list[str]) -> list[str]:
        valid_fallbacks = []
        for fallback_uuid in fallback_uuids:
            if fallback_uuid in config_schema.NONE_SENTINELS:
                continue
            try:
                await self.ap.model_mgr.get_model_by_uuid(fallback_uuid)
                valid_fallbacks.append(fallback_uuid)
            except ValueError:
                self.ap.logger.warning(f'Fallback model {fallback_uuid} not found, skipping')
        return valid_fallbacks

    def _runner_accepts_multimodal_input(self, descriptor: AgentRunnerDescriptor | None) -> bool:
        if descriptor is None:
            return True
        return descriptor.capabilities.get('multimodal_input', False)

    def _model_supports_vision(self, llm_model: typing.Any | None) -> bool:
        if not llm_model:
            return False
        abilities = getattr(getattr(llm_model, 'model_entity', None), 'abilities', [])
        return 'vision' in (abilities or [])

    def _should_keep_image_inputs(
        self,
        descriptor: AgentRunnerDescriptor | None,
        uses_host_models: bool,
        llm_model: typing.Any | None,
    ) -> bool:
        if not self._runner_accepts_multimodal_input(descriptor):
            return False
        if uses_host_models:
            return self._model_supports_vision(llm_model)
        return True

    def _strip_images_from_history(self, query: pipeline_query.Query) -> None:
        for msg in query.messages:
            if isinstance(msg.content, list):
                msg.content = [elem for elem in msg.content if elem.type != 'image_url']

    def _has_declared_db_engine(self) -> bool:
        persistence_mgr = getattr(self.ap, 'persistence_mgr', None)
        if persistence_mgr is None:
            return False
        if 'get_db_engine' in getattr(persistence_mgr, '__dict__', {}):
            return True
        return hasattr(type(persistence_mgr), 'get_db_engine')

    async def _load_agent_runner_history_messages(
        self,
        runner_id: str | None,
        conversation_uuid: str | None,
    ) -> list[provider_message.Message] | None:
        if not runner_id or not conversation_uuid or not self._has_declared_db_engine():
            return None

        try:
            from ...agent.runner.transcript_store import TranscriptStore

            store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())
            messages = await store.get_legacy_provider_messages(str(conversation_uuid))
        except Exception as e:
            self.ap.logger.warning(
                f'Unable to load Transcript history view for conversation {conversation_uuid}: {e}'
            )
            return None

        return messages or None

    async def _resolve_history_messages(
        self,
        runner_id: str | None,
        conversation: typing.Any,
    ) -> list[provider_message.Message]:
        transcript_messages = await self._load_agent_runner_history_messages(
            runner_id,
            getattr(conversation, 'uuid', None),
        )
        if transcript_messages is not None:
            return transcript_messages
        return conversation.messages.copy()

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """Process"""
        # Resolve runner ID from the current ai.runner.id shape.
        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)

        # Get runner config from ai.runner_config[runner_id].
        runner_config = ConfigMigration.resolve_runner_config(query.pipeline_config, runner_id) if runner_id else {}
        query.variables = query.variables or {}
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
        bound_mcp_servers = query.variables.get('_pipeline_bound_mcp_servers', None)
        descriptor = await self._get_runner_descriptor(runner_id, bound_plugins)

        session = await self.ap.sess_mgr.get_session(query)

        uses_host_models = config_schema.uses_host_models(descriptor)
        uses_host_tools = config_schema.uses_host_tools(descriptor)
        include_skill_authoring = (
            config_schema.supports_skill_authoring(descriptor)
            and getattr(self.ap, 'skill_service', None) is not None
        )
        inject_skill_context = config_schema.supports_skill_injection(descriptor)
        llm_model = None
        if uses_host_models:
            primary_uuid, fallback_uuids = config_schema.extract_model_selection(descriptor, runner_config)
            llm_model = await self._resolve_llm_model(primary_uuid)
            valid_fallbacks = await self._resolve_fallback_models(fallback_uuids)
            if valid_fallbacks:
                query.variables['_fallback_model_uuids'] = valid_fallbacks

        prompt_config = config_schema.extract_prompt_config(descriptor, runner_config, DEFAULT_PROMPT_CONFIG)

        conversation = await self.ap.sess_mgr.get_conversation(
            query,
            session,
            prompt_config,
            query.pipeline_uuid,
            query.bot_uuid,
        )

        # Expire externally managed conversation ids after the conversation has
        # been idle for longer than the configured conversation expire time.
        # The idle window is measured from the last preprocess/update time, not
        # from the conversation creation time.
        conversation_expire_time = ConfigMigration.get_expire_time(query.pipeline_config)
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
        query.messages = await self._resolve_history_messages(runner_id, conversation)

        if uses_host_models:
            query.use_funcs = []
            if llm_model:
                query.use_llm_model_uuid = llm_model.model_entity.uuid

                if uses_host_tools and 'func_call' in (llm_model.model_entity.abilities or []):
                    query.use_funcs = await self.ap.tool_mgr.get_all_tools(
                        bound_plugins,
                        bound_mcp_servers,
                        include_skill_authoring=include_skill_authoring,
                    )

                    self.ap.logger.debug(f'Bound plugins: {bound_plugins}')
                    self.ap.logger.debug(f'Bound MCP servers: {bound_mcp_servers}')
                    self.ap.logger.debug(f'Use funcs: {query.use_funcs}')

            # If primary model doesn't support func_call but fallback models exist,
            # load tools anyway since fallback models may support them
            if uses_host_tools and not query.use_funcs and query.variables.get('_fallback_model_uuids'):
                query.use_funcs = await self.ap.tool_mgr.get_all_tools(
                    bound_plugins,
                    bound_mcp_servers,
                    include_skill_authoring=include_skill_authoring,
                )
        elif uses_host_tools:
            query.use_funcs = await self.ap.tool_mgr.get_all_tools(
                bound_plugins,
                bound_mcp_servers,
                include_skill_authoring=include_skill_authoring,
            )

            self.ap.logger.debug(f'Bound plugins: {bound_plugins}')
            self.ap.logger.debug(f'Bound MCP servers: {bound_mcp_servers}')
            self.ap.logger.debug(f'Use funcs: {query.use_funcs}')

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

        keep_image_inputs = self._should_keep_image_inputs(descriptor, uses_host_models, llm_model)
        if not keep_image_inputs:
            self._strip_images_from_history(query)

        content_list: list[provider_message.ContentElement] = []

        plain_text = ''
        quote_msg = query.pipeline_config['trigger'].get('misc', {}).get('combine-quote-message', False)

        for me in query.message_chain:
            if isinstance(me, platform_message.Plain):
                content_list.append(provider_message.ContentElement.from_text(me.text))
                plain_text += me.text
            elif isinstance(me, platform_message.Image):
                if keep_image_inputs:
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
                        if keep_image_inputs:
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

        # Extract configured KB UUIDs into query variables so PromptPreProcessing
        # plugins can still adjust the authorized retrieval set before run_agent.
        query.variables['_knowledge_base_uuids'] = config_schema.extract_knowledge_base_uuids(
            descriptor,
            runner_config,
        )

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

        # =========== Skill awareness for capable runners ===========
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
        if inject_skill_context and self.ap.skill_mgr:
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
