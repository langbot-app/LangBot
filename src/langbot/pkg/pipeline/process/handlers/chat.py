from __future__ import annotations

import uuid
import typing
import traceback
import time
from datetime import datetime


from .. import handler
from ... import entities
from ... import plugin_diagnostics

import langbot_plugin.api.entities.events as events
from ....agent.runner.config_migration import ConfigMigration
from ....agent.runner import config_schema
from ....utils import constants, runner as runner_utils
from ....telemetry import features as telemetry_features
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


DEFAULT_PROMPT_CONFIG = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
]


class ChatMessageHandler(handler.MessageHandler):
    """Chat message handler using AgentRunOrchestrator.

    This handler delegates all runner execution to the agent_run_orchestrator,
    which resolves runner ID, builds context, invokes plugin runtime,
    and normalizes results.
    """

    async def handle(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[entities.StageProcessResult, None]:
        """Handle chat message by delegating to AgentRunOrchestrator."""
        # Trigger plugin event
        event_class = (
            events.PersonNormalMessageReceived
            if query.launcher_type == provider_session.LauncherTypes.PERSON
            else events.GroupNormalMessageReceived
        )

        event = event_class(
            launcher_type=query.launcher_type.value,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
            text_message=str(query.message_chain),
            message_event=query.message_event,
            message_chain=query.message_chain,
            query=query,
        )

        # Get bound plugins for filtering
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
        event_ctx = await self.ap.plugin_connector.emit_event(event, bound_plugins)

        is_create_card = False  # Track if streaming card was created

        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is not None:
                mc = event_ctx.event.reply_message_chain
                plugin_diagnostics.record_pending_plugin_response_source(
                    query,
                    mc,
                    plugin_diagnostics.get_response_sources(event_ctx),
                    plugin_diagnostics.get_emitted_plugins(event_ctx),
                    event.event_name,
                )
                query.resp_messages.append(mc)

                yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
            else:
                self.ap.logger.debug(
                    f'NormalMessageReceived event prevented default for query {query.query_id} without reply'
                )
                yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
        else:
            if event_ctx.event.user_message_alter is not None:
                if isinstance(event_ctx.event.user_message_alter, list):
                    query.user_message.content = event_ctx.event.user_message_alter
                elif isinstance(event_ctx.event.user_message_alter, str):
                    query.user_message.content = [
                        provider_message.ContentElement.from_text(event_ctx.event.user_message_alter)
                    ]
                elif isinstance(event_ctx.event.user_message_alter, provider_message.ContentElement):
                    query.user_message.content = [event_ctx.event.user_message_alter]

            text_length = 0
            try:
                # Mark start time for telemetry
                start_ts = time.time()

                try_claim_steering = getattr(
                    self.ap.agent_run_orchestrator,
                    'try_claim_steering_from_query',
                    None,
                )
                if try_claim_steering and await try_claim_steering(query):
                    yield entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
                    return

                try:
                    is_stream = await query.adapter.is_stream_output_supported()
                except AttributeError:
                    is_stream = False

                # Create a single resp_message_id for the entire streaming response
                resp_message_id = uuid.uuid4()
                chunk_count = 0

                # Use AgentRunOrchestrator to run the agent
                # This replaces direct runner lookup and PluginAgentRunnerWrapper
                async for result in self.ap.agent_run_orchestrator.run_from_query(query):
                    result.resp_message_id = str(resp_message_id)

                    # For streaming mode, pop previous response before adding new chunk
                    # This allows incremental card updates
                    if is_stream:
                        if query.resp_messages:
                            query.resp_messages.pop()
                        if query.resp_message_chain:
                            query.resp_message_chain.pop()

                        # Create streaming card on first result (connection established)
                        if not is_create_card:
                            await query.adapter.create_message_card(str(resp_message_id), query.message_event)
                            is_create_card = True

                    query.resp_messages.append(result)

                    if is_stream:
                        chunk_count += 1
                        # Only log every 10th chunk to reduce excessive logging during streaming.
                        # First chunk uses INFO level to confirm connection establishment.
                        if chunk_count == 1:
                            summary = self.format_result_log(result)
                            if summary is not None:
                                self.ap.logger.info(f'Conversation({query.query_id}) Streaming started: {summary}')
                            else:
                                self.ap.logger.info(f'Conversation({query.query_id}) Streaming started')
                        elif chunk_count % 10 == 0:
                            self.ap.logger.debug(
                                f'Conversation({query.query_id}) Streaming chunk {chunk_count}: {self.cut_str(result.readable_str())}'
                            )
                    else:
                        summary = self.format_result_log(result)
                        if summary is not None:
                            self.ap.logger.info(f'Conversation({query.query_id}) Response: {summary}')

                    if result.content is not None:
                        text_length += len(result.content)

                    yield entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

                # Log final summary after streaming completes
                if is_stream:
                    self.ap.logger.info(
                        f'Conversation({query.query_id}) Streaming completed: {chunk_count} chunks, {text_length} chars'
                    )

                # Keep a conversation object available for downstream legacy
                # readers, but do not mirror AgentRunner history into
                # conversation.messages. TranscriptStore is the canonical
                # history source for this path.
                await self._ensure_conversation_for_history(query)

            except Exception as e:
                # Import orchestrator errors for specific handling
                from ....agent.runner.errors import (
                    RunnerNotFoundError,
                    RunnerNotAuthorizedError,
                    RunnerExecutionError,
                )

                error_info = f'{traceback.format_exc()}'
                self.ap.logger.error(f'Conversation({query.query_id}) Request Failed: {error_info}')

                # Handle specific runner errors with appropriate messages
                if isinstance(e, RunnerNotFoundError):
                    user_notice = f'Agent runner not found: {e.runner_id}'
                elif isinstance(e, RunnerNotAuthorizedError):
                    user_notice = 'Agent runner not authorized for this pipeline'
                elif isinstance(e, RunnerExecutionError):
                    if e.retryable:
                        user_notice = 'Agent runner temporarily unavailable. Please try again.'
                    else:
                        user_notice = 'Agent runner execution failed.'
                else:
                    # Use existing exception handling
                    exception_handling = query.pipeline_config['output']['misc'].get('exception-handling', 'show-hint')

                    if exception_handling == 'show-error':
                        user_notice = f'{e}'
                    elif exception_handling == 'show-hint':
                        user_notice = query.pipeline_config['output']['misc'].get('failure-hint', 'Request failed.')
                    else:  # hide
                        user_notice = None

                yield entities.StageProcessResult(
                    result_type=entities.ResultType.INTERRUPT,
                    new_query=query,
                    user_notice=user_notice,
                    error_notice=f'{e}',
                    debug_notice=traceback.format_exc(),
                )
            finally:
                # Telemetry reporting
                try:
                    end_ts = time.time()
                    duration_ms = None
                    if 'start_ts' in locals():
                        duration_ms = int((end_ts - start_ts) * 1000)

                    adapter_name = query.adapter.__class__.__name__ if hasattr(query, 'adapter') else None

                    # Use orchestrator to resolve runner ID for telemetry
                    runner_name = self.ap.agent_run_orchestrator.resolve_runner_id_for_telemetry(query)

                    # Model name if available
                    model_name = None
                    try:
                        if getattr(query, 'use_llm_model_uuid', None):
                            m = await self.ap.model_mgr.get_model_by_uuid(query.use_llm_model_uuid)
                            if m and getattr(m, 'model_entity', None):
                                model_name = getattr(m.model_entity, 'name', None)
                    except Exception:
                        model_name = None

                    pipeline_plugins = query.variables.get('_pipeline_bound_plugins', None)

                    runner_category = runner_utils.get_runner_category_from_runner(
                        runner_name, None, query.pipeline_config
                    )

                    # Feature usage collected during query processing (tool calls,
                    # knowledge base usage, sandbox executions, activated skills, ...)
                    features = telemetry_features.collect_features(query)

                    payload = {
                        'event_type': 'query',
                        'query_id': query.query_id,
                        'adapter': adapter_name,
                        'runner': runner_name,
                        'runner_category': runner_category,
                        'duration_ms': duration_ms,
                        'model_name': model_name,
                        'version': constants.semantic_version,
                        'instance_id': constants.instance_id,
                        'edition': constants.edition,
                        'pipeline_plugins': pipeline_plugins,
                        'features': features,
                        'error': locals().get('error_info', None),
                        'timestamp': datetime.utcnow().isoformat(),
                    }

                    await self.ap.telemetry.start_send_task(payload)

                    # Trigger survey events on successful non-WebSocket responses
                    if not locals().get('error_info') and adapter_name and 'WebSocket' not in adapter_name:
                        if self.ap.survey:
                            await self.ap.survey.trigger_event('first_bot_response_success')
                            # Counts toward the bot_response_success_100 milestone event
                            await self.ap.survey.record_bot_response_success()
                except Exception as ex:
                    self.ap.logger.warning(f'Failed to send telemetry: {ex}')

    async def _ensure_conversation_for_history(
        self,
        query: pipeline_query.Query,
    ) -> provider_session.Conversation:
        session = getattr(query, 'session', None)
        conversation = getattr(session, 'using_conversation', None)
        if conversation is not None:
            return conversation

        if session is None or getattr(self.ap, 'sess_mgr', None) is None:
            raise RuntimeError('Conversation is not available for history update')

        prompt_config = await self._build_history_prompt_config(query)
        conversation = await self.ap.sess_mgr.get_conversation(
            query,
            session,
            prompt_config,
            query.pipeline_uuid,
            query.bot_uuid,
        )
        if conversation is None:
            raise RuntimeError('Conversation manager did not return a conversation')

        if getattr(session, 'using_conversation', None) is None:
            session.using_conversation = conversation
        return conversation

    async def _build_history_prompt_config(
        self,
        query: pipeline_query.Query,
    ) -> list[dict[str, typing.Any]]:
        prompt_messages = getattr(getattr(query, 'prompt', None), 'messages', None)
        if prompt_messages:
            prompt_config = []
            for message in prompt_messages:
                if hasattr(message, 'model_dump'):
                    prompt_config.append(message.model_dump(mode='python'))
                elif isinstance(message, dict):
                    prompt_config.append(message)
            if prompt_config:
                return prompt_config

        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)
        runner_config = ConfigMigration.resolve_runner_config(query.pipeline_config, runner_id) if runner_id else {}
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)
        descriptor = await self._get_runner_descriptor(runner_id, bound_plugins)
        return config_schema.extract_prompt_config(descriptor, runner_config, DEFAULT_PROMPT_CONFIG)

    async def _get_runner_descriptor(
        self,
        runner_id: str | None,
        bound_plugins: list[str] | None,
    ) -> typing.Any | None:
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
