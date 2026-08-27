from __future__ import annotations

import json
import copy
import typing
from .. import runner
from ...telemetry import features as telemetry_features
from ..modelmgr import requester as modelmgr_requester
from ..modelmgr import reasoning as modelmgr_reasoning
from ..tools.loaders.native import EXEC_TOOL_NAME
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.rag.context as rag_context

from ...pipeline.pool import get_query_execution_context

rag_combined_prompt_template = """
The following are relevant context entries retrieved from the knowledge base. 
Please use them to answer the user's message. 
Respond in the same language as the user's input.

<context>
{rag_context}
</context>

<user_message>
{user_message}
</user_message>
"""

SANDBOX_EXEC_TOOL_NAME = 'sandbox_exec'
SANDBOX_EXEC_SYSTEM_GUIDANCE = (
    'When sandbox_exec is available, use it for exact calculations, statistics, structured data parsing, '
    'and code execution instead of estimating mentally. If the user provides numbers, tables, CSV-like text, '
    'JSON, or other data and asks for a computed answer, prefer running a short Python script in sandbox_exec '
    'and then answer from the tool result.'
)


# Hard cap on tool-call rounds within a single agent turn. A looping or
# adversarial model can otherwise emit tool calls indefinitely (each potentially
# a sandbox exec), yielding a non-terminating request and runaway cost. Set
# generously so it never interrupts legitimate multi-step agentic workflows.
MAX_TOOL_CALL_ROUNDS = 128


def _model_has_ability(model: modelmgr_requester.RuntimeLLMModel, ability: str) -> bool:
    return ability in (model.model_entity.abilities or [])


class _StreamAccumulator:
    """Accumulate streamed content and fragmented OpenAI-style tool calls."""

    def __init__(
        self,
        msg_sequence: int = 0,
        initial_content: str | None = None,
        remove_think: bool = False,
    ):
        self.tool_calls_map: dict[str, provider_message.ToolCall] = {}
        self.msg_idx = 0
        self.accumulated_content = initial_content or ''
        self.last_role = 'assistant'
        self.provider_specific_fields: dict[str, typing.Any] = {}
        self.msg_sequence = msg_sequence
        self.remove_think = remove_think
        self._think_state = None
        if remove_think:
            from ..modelmgr.requesters.litellmchat import _ThinkStripState

            self._think_state = _ThinkStripState()

    def add(self, msg: provider_message.MessageChunk) -> provider_message.MessageChunk | None:
        self.msg_idx += 1

        if msg.role:
            self.last_role = msg.role

        if msg.content:
            content = msg.content
            if self._think_state is not None:
                content = self._think_state.feed(content)
            self.accumulated_content += content

        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call.id not in self.tool_calls_map:
                    self.tool_calls_map[tool_call.id] = provider_message.ToolCall(
                        id=tool_call.id,
                        type=tool_call.type,
                        function=provider_message.FunctionCall(
                            name=tool_call.function.name if tool_call.function else '',
                            arguments='',
                        ),
                        provider_specific_fields=(
                            dict(tool_call.provider_specific_fields) if tool_call.provider_specific_fields else None
                        ),
                    )
                elif tool_call.provider_specific_fields:
                    existing_fields = self.tool_calls_map[tool_call.id].provider_specific_fields or {}
                    self.tool_calls_map[tool_call.id].provider_specific_fields = {
                        **existing_fields,
                        **tool_call.provider_specific_fields,
                    }
                if tool_call.function and tool_call.function.arguments:
                    self.tool_calls_map[tool_call.id].function.arguments += tool_call.function.arguments

        if msg.provider_specific_fields:
            for key, value in msg.provider_specific_fields.items():
                if key == 'reasoning_content' and isinstance(value, str):
                    previous = self.provider_specific_fields.get(key, '')
                    self.provider_specific_fields[key] = f'{previous}{value}'
                else:
                    self.provider_specific_fields[key] = value

        if msg.is_final:
            self._flush_think_state()

        if self.msg_idx % 8 == 0 or msg.is_final:
            self.msg_sequence += 1
            return provider_message.MessageChunk(
                role=self.last_role,
                content=self._maybe_strip_think(self.accumulated_content),
                tool_calls=list(self.tool_calls_map.values()) if (self.tool_calls_map and msg.is_final) else None,
                provider_specific_fields=(self.provider_specific_fields or None) if msg.is_final else None,
                is_final=msg.is_final,
                msg_sequence=self.msg_sequence,
            )

        return None

    def final_message(self) -> provider_message.MessageChunk:
        self._flush_think_state()
        return provider_message.MessageChunk(
            role=self.last_role,
            content=self._maybe_strip_think(self.accumulated_content),
            tool_calls=list(self.tool_calls_map.values()) if self.tool_calls_map else None,
            provider_specific_fields=self.provider_specific_fields or None,
            msg_sequence=self.msg_sequence,
        )

    def _maybe_strip_think(self, content: str) -> str:
        if not self.remove_think or not content:
            return content

        from ..modelmgr.requesters.litellmchat import LiteLLMRequester

        return LiteLLMRequester._strip_think(content)

    def _flush_think_state(self) -> None:
        if self._think_state is None:
            return
        pending = self._think_state.flush()
        if pending:
            self.accumulated_content += pending


@runner.runner_class('local-agent')
class LocalAgentRunner(runner.RequestRunner):
    """Local agent request runner"""

    async def _inject_inbound_attachments(
        self,
        query: pipeline_query.Query,
        user_message: provider_message.Message,
    ) -> None:
        """Persist inbound attachments into the sandbox and tell the model.

        No-op when the box service is unavailable or there are no attachments.
        On success, appends an extra text ContentElement to the user message
        listing the in-sandbox paths and the outbox convention, and stashes the
        descriptors in ``query.variables['_sandbox_inbound_attachments']``.
        """
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None or not getattr(box_service, 'available', False):
            return
        try:
            attachments = await box_service.materialize_inbound_attachments(query)
        except Exception as e:  # never break the chat turn over attachment IO
            self.ap.logger.warning(f'Inbound attachment materialization failed: {e}')
            return
        if not attachments:
            return

        query.variables['_sandbox_inbound_attachments'] = attachments

        lines = [
            'The user sent attachments. They have been saved into the sandbox and are '
            'available to the exec/read/write tools at these paths:'
        ]
        for att in attachments:
            lines.append(f'- {att["type"]}: {att["path"]} ({att["size"]} bytes)')
        outbox_dir = f'{box_service.OUTBOX_MOUNT_DIR}/{query.query_id}'
        lines.append(
            'If you produce any file (image, audio, document, etc.) that should be sent '
            f'back to the user, write it into {outbox_dir}/ (create the directory if '
            'needed). Every file placed there will be delivered to the user automatically.'
        )
        note = '\n'.join(lines)

        # Voice/File attachments are now available to the agent via the sandbox
        # (exec/read/write tools). Their raw bytes must NOT be forwarded to the
        # chat model as multimodal content: providers reject non-image file
        # parts ("Invalid user message ... ensure all user messages are valid
        # OpenAI chat completion messages"). Strip those content elements and
        # rely on the sandbox-path note instead. Images are kept so vision
        # models can still see them.
        _model_unsafe_types = {'file_base64', 'file_url'}
        if isinstance(user_message.content, list):
            user_message.content = [
                ce for ce in user_message.content if getattr(ce, 'type', None) not in _model_unsafe_types
            ]

        if isinstance(user_message.content, str):
            user_message.content = [
                provider_message.ContentElement.from_text(user_message.content),
                provider_message.ContentElement.from_text(note),
            ]
        elif isinstance(user_message.content, list):
            user_message.content.append(provider_message.ContentElement.from_text(note))
        else:
            user_message.content = [provider_message.ContentElement.from_text(note)]

    def _build_request_messages(
        self,
        query: pipeline_query.Query,
        user_message: provider_message.Message,
    ) -> list[provider_message.Message]:
        req_messages = query.prompt.messages.copy() + query.messages.copy()

        if any(getattr(tool, 'name', None) == EXEC_TOOL_NAME for tool in query.use_funcs or []):
            req_messages.append(
                provider_message.Message(
                    role='system',
                    content=self.ap.box_service.get_system_guidance(query),
                )
            )

        req_messages.append(user_message)
        return req_messages

    async def _get_model_candidates(
        self,
        query: pipeline_query.Query,
    ) -> list[modelmgr_requester.RuntimeLLMModel]:
        """Build ordered list of models to try: primary model + fallback models."""
        candidates = []
        execution_context = get_query_execution_context(query)

        # Primary model
        if query.use_llm_model_uuid:
            try:
                primary = await self.ap.model_mgr.get_model_by_uuid(
                    execution_context,
                    query.use_llm_model_uuid,
                )
            except ValueError:
                self.ap.logger.warning(f'Primary model {query.use_llm_model_uuid} not found')
            else:
                candidates.append(LocalAgentRunner._apply_pipeline_reasoning_config(query, primary))

        # Fallback models
        fallback_uuids = (query.variables or {}).get('_fallback_model_uuids', [])
        for fb_uuid in fallback_uuids:
            try:
                fb_model = await self.ap.model_mgr.get_model_by_uuid(
                    execution_context,
                    fb_uuid,
                )
            except ValueError:
                self.ap.logger.warning(f'Fallback model {fb_uuid} not found, skipping')
            else:
                candidates.append(LocalAgentRunner._apply_pipeline_reasoning_config(query, fb_model))

        return candidates

    @staticmethod
    def _apply_pipeline_reasoning_config(
        query: pipeline_query.Query,
        model: modelmgr_requester.RuntimeLLMModel,
    ) -> modelmgr_requester.RuntimeLLMModel:
        local_agent_config = query.pipeline_config.get('ai', {}).get('local-agent', {})
        model_config = local_agent_config.get('model', {})
        reasoning_by_model = model_config.get('reasoning', {}) if isinstance(model_config, dict) else {}
        level = (
            reasoning_by_model.get(model.model_entity.uuid, 'provider_default')
            if isinstance(reasoning_by_model, dict)
            else 'provider_default'
        )
        reasoning_config = modelmgr_reasoning.normalize_reasoning_config({'level': level})
        configured_model = copy.copy(model)
        configured_model.reasoning_config_override = reasoning_config
        return configured_model

    async def _invoke_with_fallback(
        self,
        query: pipeline_query.Query,
        candidates: list[modelmgr_requester.RuntimeLLMModel],
        messages: list,
        funcs: list,
        remove_think: bool,
    ) -> tuple[provider_message.Message, modelmgr_requester.RuntimeLLMModel]:
        """Try non-streaming invocation with sequential fallback. Returns (message, model_used)."""
        last_error = None
        for model in candidates:
            try:
                msg = await model.provider.invoke_llm(
                    query,
                    model,
                    messages,
                    funcs if _model_has_ability(model, 'func_call') else [],
                    extra_args=model.model_entity.extra_args,
                    remove_think=remove_think,
                )
                return msg, model
            except Exception as e:
                last_error = e
                self.ap.logger.warning(f'Model {model.model_entity.name} failed: {e}, trying next fallback...')
        raise last_error or RuntimeError('No model candidates available')

    async def _invoke_stream_with_fallback(
        self,
        query: pipeline_query.Query,
        candidates: list[modelmgr_requester.RuntimeLLMModel],
        messages: list,
        funcs: list,
        remove_think: bool,
    ) -> tuple[typing.AsyncGenerator, modelmgr_requester.RuntimeLLMModel]:
        """Try streaming invocation with sequential fallback. Returns (stream_generator, model_used).

        Fallback is only possible before any chunks have been yielded to the client.
        Once streaming starts, the model is committed.
        """
        last_error = None
        for model in candidates:
            try:
                stream = model.provider.invoke_llm_stream(
                    query,
                    model,
                    messages,
                    funcs if _model_has_ability(model, 'func_call') else [],
                    extra_args=model.model_entity.extra_args,
                    remove_think=remove_think,
                )
                # Attempt to get the first chunk to verify the stream works
                first_chunk = await stream.__anext__()

                async def _chain_stream(first, rest):
                    yield first
                    async for chunk in rest:
                        yield chunk

                return _chain_stream(first_chunk, stream), model
            except StopAsyncIteration:
                # Empty stream — treat as success (model returned nothing)
                async def _empty_stream():
                    return
                    yield  # make it a generator

                return _empty_stream(), model
            except Exception as e:
                last_error = e
                self.ap.logger.warning(f'Model {model.model_entity.name} stream failed: {e}, trying next fallback...')
        raise last_error or RuntimeError('No model candidates available')

    async def run(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run request"""
        pending_tool_calls = []
        initial_response_emitted = False

        # Get knowledge bases list from query variables (set by PreProcessor,
        # may have been modified by plugins during PromptPreProcessing)
        kb_uuids = query.variables.get('_knowledge_base_uuids', [])

        user_message = copy.deepcopy(query.user_message)

        # Materialize inbound attachments (images / voices / files) into the
        # sandbox so the agent's exec/read/write tools can operate on the real
        # bytes — not just the multimodal copy the model sees. The exact
        # in-sandbox paths are announced to the model as a system note.
        await self._inject_inbound_attachments(query, user_message)

        user_message_text = ''

        if isinstance(user_message.content, str):
            user_message_text = user_message.content
        elif isinstance(user_message.content, list):
            for ce in user_message.content:
                if ce.type == 'text':
                    user_message_text += ce.text
                    break

        if kb_uuids and user_message_text:
            # only support text for now
            all_results: list[rag_context.RetrievalResultEntry] = []
            execution_context = get_query_execution_context(query)

            kb_engine_plugins: set[str] = set()

            # Retrieve from each knowledge base
            for kb_uuid in kb_uuids:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(execution_context, kb_uuid)

                if not kb:
                    self.ap.logger.warning(f'Knowledge base {kb_uuid} not found, skipping')
                    continue

                try:
                    engine_plugin_id = kb.get_knowledge_engine_plugin_id() or 'builtin'
                except Exception:
                    engine_plugin_id = 'builtin'
                kb_engine_plugins.add(engine_plugin_id)

                result = await kb.retrieve(
                    execution_context,
                    user_message_text,
                    settings={
                        'bot_uuid': query.bot_uuid or '',
                        'sender_id': str(query.sender_id),
                        'session_name': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                    },
                )

                if result:
                    all_results.extend(result)

            # Telemetry: knowledge base usage (counts and engine categories only)
            telemetry_features.set_value(
                query,
                'kb',
                {
                    'kb_count': len(kb_uuids),
                    'engine_plugins': sorted(kb_engine_plugins),
                    'retrieved_entries': len(all_results),
                },
            )

            # Rerank step: re-score results using a rerank model if configured
            local_agent_config = query.pipeline_config.get('ai', {}).get('local-agent', {})
            rerank_model_uuid = local_agent_config.get('rerank-model', '')
            if rerank_model_uuid == '__none__':
                rerank_model_uuid = ''
            self.ap.logger.info(
                f'Rerank config: model_uuid={rerank_model_uuid!r}, '
                f'results={len(all_results)}, '
                f'local_agent_keys={list(local_agent_config.keys())}'
            )
            if all_results and rerank_model_uuid:
                try:
                    rerank_model = await self.ap.model_mgr.get_rerank_model_by_uuid(
                        execution_context,
                        rerank_model_uuid,
                    )
                    rerank_top_k = int(local_agent_config.get('rerank-top-k', 5))

                    doc_texts = []
                    for entry in all_results:
                        text = ' '.join(c.text for c in entry.content if c.type == 'text' and c.text)
                        doc_texts.append(text)

                    doc_texts_capped = doc_texts[:64]
                    scores = await rerank_model.provider.invoke_rerank(
                        model=rerank_model,
                        query=user_message_text,
                        documents=doc_texts_capped,
                        execution_context=execution_context,
                    )

                    scored = sorted(scores, key=lambda x: x.get('relevance_score', 0), reverse=True)
                    top_indices = [s['index'] for s in scored[:rerank_top_k] if s['index'] < len(all_results)]
                    all_results = [all_results[i] for i in top_indices]

                    self.ap.logger.info(
                        f'Rerank complete: {len(doc_texts)} docs reranked -> top {len(all_results)} kept (top_k={rerank_top_k})'
                    )
                except ValueError:
                    self.ap.logger.warning(f'Rerank model {rerank_model_uuid} not found, skipping rerank')
                except Exception as e:
                    self.ap.logger.warning(f'Rerank failed, using original order: {e}')

            final_user_message_text = ''

            if all_results:
                texts = []
                idx = 1
                for entry in all_results:
                    for content in entry.content:
                        if content.type == 'text' and content.text is not None:
                            texts.append(f'[{idx}] {content.text}')
                            idx += 1
                rag_context_text = '\n\n'.join(texts)
                final_user_message_text = rag_combined_prompt_template.format(
                    rag_context=rag_context_text, user_message=user_message_text
                )

            else:
                final_user_message_text = user_message_text

            self.ap.logger.debug(f'Final user message text: {final_user_message_text}')

            for ce in user_message.content:
                if ce.type == 'text':
                    ce.text = final_user_message_text
                    break

        mcp_loader = getattr(getattr(self.ap, 'tool_mgr', None), 'mcp_tool_loader', None)
        if mcp_loader is not None:
            resource_context = await mcp_loader.build_resource_context_for_query(query)
            if resource_context:
                resource_addition = (
                    '\n\nMCP resource context selected by LangBot host:\n'
                    f'{resource_context}\n\n'
                    'Use this context as read-only reference material. If it conflicts with the user message, '
                    'ask for clarification before taking external actions.'
                )
                if isinstance(user_message.content, str):
                    user_message.content += resource_addition
                elif isinstance(user_message.content, list):
                    appended = False
                    for ce in user_message.content:
                        if ce.type == 'text':
                            ce.text = (ce.text or '') + resource_addition
                            appended = True
                            break
                    if not appended:
                        user_message.content.append(
                            provider_message.ContentElement.from_text(resource_addition.strip())
                        )

        req_messages = self._build_request_messages(query, user_message)

        try:
            is_stream = await query.adapter.is_stream_output_supported()
        except AttributeError:
            is_stream = False

        remove_think = ((query.pipeline_config.get('output') or {}).get('misc') or {}).get('remove-think', False)

        # Build ordered candidate list (primary + fallbacks)
        candidates = await self._get_model_candidates(query)
        if not candidates:
            raise RuntimeError('No LLM model configured for local-agent runner')

        self.ap.logger.debug(
            f'localagent req: query={query.query_id} req_messages={req_messages} '
            f'candidates={[m.model_entity.name for m in candidates]}'
        )

        if not is_stream:
            # Non-streaming: invoke with fallback
            msg, use_llm_model = await self._invoke_with_fallback(
                query,
                candidates,
                req_messages,
                query.use_funcs,
                remove_think,
            )
            final_msg = msg
        else:
            # Streaming: invoke with fallback
            stream_accumulator = _StreamAccumulator(msg_sequence=1, remove_think=remove_think)

            stream_src, use_llm_model = await self._invoke_stream_with_fallback(
                query,
                candidates,
                req_messages,
                query.use_funcs,
                remove_think,
            )
            async for msg in stream_src:
                chunk = stream_accumulator.add(msg)
                if chunk:
                    yield chunk
                    initial_response_emitted = True

            final_msg = stream_accumulator.final_message()

        pending_tool_calls = final_msg.tool_calls
        if isinstance(final_msg, provider_message.MessageChunk):
            first_end_sequence = final_msg.msg_sequence

        if not is_stream:
            yield final_msg
        elif not initial_response_emitted:
            yield final_msg
            initial_response_emitted = True

        req_messages.append(final_msg)

        # Once a model succeeds, commit to it for the tool call loop
        # (no fallback mid-conversation — different models may interpret tool results differently)
        tool_call_round = 0
        while pending_tool_calls:
            tool_call_round += 1
            telemetry_features.set_value(query, 'tool_call_rounds', tool_call_round)
            if tool_call_round > MAX_TOOL_CALL_ROUNDS:
                self.ap.logger.warning(
                    f'Tool-call loop reached the {MAX_TOOL_CALL_ROUNDS}-round cap '
                    f'(query_id={query.query_id}); stopping to avoid a non-terminating request.'
                )
                break
            for tool_call in pending_tool_calls:
                try:
                    func = tool_call.function

                    if func.arguments:
                        parameters = json.loads(func.arguments)
                    else:
                        parameters = {}

                    func_ret = await self.ap.tool_mgr.execute_func_call(func.name, parameters, query=query)

                    # Handle return value content
                    tool_content = None
                    if (
                        isinstance(func_ret, list)
                        and len(func_ret) > 0
                        and isinstance(func_ret[0], provider_message.ContentElement)
                    ):
                        # OpenAI-compatible APIs require tool-message content to be a
                        # string; a raw list of ContentElement causes HTTP 500 (#2457).
                        tool_content = '\n'.join(str(ce) for ce in func_ret)
                    else:
                        tool_content = json.dumps(func_ret, ensure_ascii=False)

                    if is_stream:
                        msg = provider_message.MessageChunk(
                            role='tool',
                            content=tool_content,
                            tool_call_id=tool_call.id,
                        )
                    else:
                        msg = provider_message.Message(
                            role='tool',
                            content=tool_content,
                            tool_call_id=tool_call.id,
                        )

                    yield msg

                    req_messages.append(msg)
                except Exception as e:
                    if is_stream:
                        err_msg = provider_message.MessageChunk(
                            role='tool',
                            content=f'err: {e}',
                            tool_call_id=tool_call.id,
                            is_final=True,
                        )
                    else:
                        err_msg = provider_message.Message(role='tool', content=f'err: {e}', tool_call_id=tool_call.id)

                    yield err_msg

                    req_messages.append(err_msg)

            self.ap.logger.debug(
                f'localagent req: query={query.query_id} req_messages={req_messages} '
                f'use_llm_model={use_llm_model.model_entity.name}'
            )

            if is_stream:
                # Do NOT re-seed the accumulator with first_content:
                # the previous round's text was already pushed to the
                # platform adapter. Re-seeding would cause every
                # subsequent round to repeat the entire opening line,
                # which the platform then forwards as a duplicate message.
                stream_accumulator = _StreamAccumulator(
                    msg_sequence=first_end_sequence,
                    remove_think=remove_think,
                )

                tool_stream_src = use_llm_model.provider.invoke_llm_stream(
                    query,
                    use_llm_model,
                    req_messages,
                    query.use_funcs if _model_has_ability(use_llm_model, 'func_call') else [],
                    extra_args=use_llm_model.model_entity.extra_args,
                    remove_think=remove_think,
                )
                async for msg in tool_stream_src:
                    chunk = stream_accumulator.add(msg)
                    if chunk:
                        yield chunk

                final_msg = stream_accumulator.final_message()
            else:
                # Non-streaming: use committed model directly (no fallback in tool loop)
                msg = await use_llm_model.provider.invoke_llm(
                    query,
                    use_llm_model,
                    req_messages,
                    query.use_funcs if _model_has_ability(use_llm_model, 'func_call') else [],
                    extra_args=use_llm_model.model_entity.extra_args,
                    remove_think=remove_think,
                )

                yield msg
                final_msg = msg

            pending_tool_calls = final_msg.tool_calls

            req_messages.append(final_msg)
