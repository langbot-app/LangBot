from __future__ import annotations

import json
import copy
import typing
from .. import runner
from ..modelmgr import requester as modelmgr_requester
from ..tools.loaders.native import EXEC_TOOL_NAME
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.rag.context as rag_context
from ...skill.activation import prepare_skill_activation


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


@runner.runner_class('local-agent')
class LocalAgentRunner(runner.RequestRunner):
    """Local agent request runner"""

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
                    content=self.ap.box_service.get_system_guidance(),
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

        # Primary model
        if query.use_llm_model_uuid:
            try:
                primary = await self.ap.model_mgr.get_model_by_uuid(query.use_llm_model_uuid)
                candidates.append(primary)
            except ValueError:
                self.ap.logger.warning(f'Primary model {query.use_llm_model_uuid} not found')

        # Fallback models
        fallback_uuids = (query.variables or {}).get('_fallback_model_uuids', [])
        for fb_uuid in fallback_uuids:
            try:
                fb_model = await self.ap.model_mgr.get_model_by_uuid(fb_uuid)
                candidates.append(fb_model)
            except ValueError:
                self.ap.logger.warning(f'Fallback model {fb_uuid} not found, skipping')

        return candidates

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
                    funcs if model.model_entity.abilities.__contains__('func_call') else [],
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
                    funcs if model.model_entity.abilities.__contains__('func_call') else [],
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

        # Get knowledge bases list from query variables (set by PreProcessor,
        # may have been modified by plugins during PromptPreProcessing)
        kb_uuids = query.variables.get('_knowledge_base_uuids', [])

        user_message = copy.deepcopy(query.user_message)

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

            # Retrieve from each knowledge base
            for kb_uuid in kb_uuids:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)

                if not kb:
                    self.ap.logger.warning(f'Knowledge base {kb_uuid} not found, skipping')
                    continue

                result = await kb.retrieve(
                    user_message_text,
                    settings={
                        'bot_uuid': query.bot_uuid or '',
                        'sender_id': str(query.sender_id),
                        'session_name': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                    },
                )

                if result:
                    all_results.extend(result)

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

        req_messages = self._build_request_messages(query, user_message)

        try:
            is_stream = await query.adapter.is_stream_output_supported()
        except AttributeError:
            is_stream = False

        remove_think = query.pipeline_config['output'].get('misc', '').get('remove-think')

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
            yield msg
            final_msg = msg
        else:
            # Streaming: invoke with fallback
            tool_calls_map: dict[str, provider_message.ToolCall] = {}
            msg_idx = 0
            accumulated_content = ''
            last_role = 'assistant'
            msg_sequence = 1

            stream_src, use_llm_model = await self._invoke_stream_with_fallback(
                query,
                candidates,
                req_messages,
                query.use_funcs,
                remove_think,
            )
            async for msg in stream_src:
                msg_idx = msg_idx + 1

                if msg.role:
                    last_role = msg.role

                if msg.content:
                    accumulated_content += msg.content

                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if tool_call.id not in tool_calls_map:
                            tool_calls_map[tool_call.id] = provider_message.ToolCall(
                                id=tool_call.id,
                                type=tool_call.type,
                                function=provider_message.FunctionCall(
                                    name=tool_call.function.name if tool_call.function else '', arguments=''
                                ),
                            )
                        if tool_call.function and tool_call.function.arguments:
                            tool_calls_map[tool_call.id].function.arguments += tool_call.function.arguments

                if msg_idx % 8 == 0 or msg.is_final:
                    msg_sequence += 1
                    yield provider_message.MessageChunk(
                        role=last_role,
                        content=accumulated_content,
                        tool_calls=list(tool_calls_map.values()) if (tool_calls_map and msg.is_final) else None,
                        is_final=msg.is_final,
                        msg_sequence=msg_sequence,
                    )

            final_msg = provider_message.MessageChunk(
                role=last_role,
                content=accumulated_content,
                tool_calls=list(tool_calls_map.values()) if tool_calls_map else None,
                msg_sequence=msg_sequence,
            )

        pending_tool_calls = final_msg.tool_calls
        first_content = final_msg.content
        if isinstance(final_msg, provider_message.MessageChunk):
            first_end_sequence = final_msg.msg_sequence

        # =========== Skill activation detection ===========
        # Check if the LLM response contains a skill activation marker
        if first_content and self.ap.skill_mgr:
            original_use_funcs = query.use_funcs
            original_variables = copy.deepcopy(query.variables) if query.variables is not None else None
            original_req_messages_len = len(req_messages)

            try:
                activation = prepare_skill_activation(self.ap, query, first_content)
                if activation:
                    self.ap.logger.info(
                        f'Skill activations detected: {activation.activated_skill_names}'
                    )

                    skill_system_msg = provider_message.Message(role='system', content=activation.prompt)

                    # Reconstruct messages: keep original + add skill prompt + let LLM continue
                    req_messages.append(final_msg)
                    req_messages.append(skill_system_msg)

                    # Make another request to let the LLM execute the skill
                    if is_stream:
                        tool_calls_map = {}
                        msg_idx = 0
                        accumulated_content = activation.cleaned_content
                        last_role = 'assistant'
                        msg_sequence = first_end_sequence

                        async for msg in use_llm_model.provider.requester.invoke_llm_stream(
                            query,
                            use_llm_model,
                            req_messages,
                            query.use_funcs,
                            extra_args=use_llm_model.model_entity.extra_args,
                            remove_think=remove_think,
                        ):
                            msg_idx += 1

                            if msg.role:
                                last_role = msg.role

                            if msg.content:
                                accumulated_content += msg.content

                            if msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    if tool_call.id not in tool_calls_map:
                                        tool_calls_map[tool_call.id] = provider_message.ToolCall(
                                            id=tool_call.id,
                                            type=tool_call.type,
                                            function=provider_message.FunctionCall(
                                                name=tool_call.function.name if tool_call.function else '',
                                                arguments='',
                                            ),
                                        )
                                    if tool_call.function and tool_call.function.arguments:
                                        tool_calls_map[tool_call.id].function.arguments += tool_call.function.arguments

                            if msg_idx % 8 == 0 or msg.is_final:
                                msg_sequence += 1
                                yield provider_message.MessageChunk(
                                    role=last_role,
                                    content=accumulated_content,
                                    tool_calls=list(tool_calls_map.values()) if (tool_calls_map and msg.is_final) else None,
                                    is_final=msg.is_final,
                                    msg_sequence=msg_sequence,
                                )

                        final_msg = provider_message.MessageChunk(
                            role=last_role,
                            content=accumulated_content,
                            tool_calls=list(tool_calls_map.values()) if tool_calls_map else None,
                            msg_sequence=msg_sequence,
                        )
                        first_content = accumulated_content
                        first_end_sequence = msg_sequence
                    else:
                        msg = await use_llm_model.provider.requester.invoke_llm(
                            query,
                            use_llm_model,
                            req_messages,
                            query.use_funcs,
                            extra_args=use_llm_model.model_entity.extra_args,
                            remove_think=remove_think,
                        )
                        yield msg
                        final_msg = msg
                        first_content = msg.content

                    # Update pending tool calls from the new response
                    pending_tool_calls = final_msg.tool_calls
                    # Remove the messages we added (the original final_msg and skill_system_msg)
                    req_messages = req_messages[:-2]
            except Exception:
                self.ap.logger.exception('Skill activation failed, falling back to normal execution')
                query.use_funcs = original_use_funcs
                query.variables = original_variables
                req_messages = req_messages[:original_req_messages_len]

        req_messages.append(final_msg)

        # Once a model succeeds, commit to it for the tool call loop
        # (no fallback mid-conversation — different models may interpret tool results differently)
        while pending_tool_calls:
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
                        tool_content = func_ret
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
                tool_calls_map = {}
                msg_idx = 0
                accumulated_content = ''
                last_role = 'assistant'
                msg_sequence = first_end_sequence

                tool_stream_src = use_llm_model.provider.invoke_llm_stream(
                    query,
                    use_llm_model,
                    req_messages,
                    query.use_funcs if use_llm_model.model_entity.abilities.__contains__('func_call') else [],
                    extra_args=use_llm_model.model_entity.extra_args,
                    remove_think=remove_think,
                )
                async for msg in tool_stream_src:
                    msg_idx += 1

                    if msg.role:
                        last_role = msg.role

                    # Prepend first-round content on first chunk of tool-call round
                    if msg_idx == 1:
                        accumulated_content = first_content if first_content is not None else accumulated_content

                    if msg.content:
                        accumulated_content += msg.content

                    if msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if tool_call.id not in tool_calls_map:
                                tool_calls_map[tool_call.id] = provider_message.ToolCall(
                                    id=tool_call.id,
                                    type=tool_call.type,
                                    function=provider_message.FunctionCall(
                                        name=tool_call.function.name if tool_call.function else '', arguments=''
                                    ),
                                )
                            if tool_call.function and tool_call.function.arguments:
                                tool_calls_map[tool_call.id].function.arguments += tool_call.function.arguments

                    if msg_idx % 8 == 0 or msg.is_final:
                        msg_sequence += 1
                        yield provider_message.MessageChunk(
                            role=last_role,
                            content=accumulated_content,
                            tool_calls=list(tool_calls_map.values()) if (tool_calls_map and msg.is_final) else None,
                            is_final=msg.is_final,
                            msg_sequence=msg_sequence,
                        )

                final_msg = provider_message.MessageChunk(
                    role=last_role,
                    content=accumulated_content,
                    tool_calls=list(tool_calls_map.values()) if tool_calls_map else None,
                    msg_sequence=msg_sequence,
                )
            else:
                # Non-streaming: use committed model directly (no fallback in tool loop)
                msg = await use_llm_model.provider.invoke_llm(
                    query,
                    use_llm_model,
                    req_messages,
                    query.use_funcs if use_llm_model.model_entity.abilities.__contains__('func_call') else [],
                    extra_args=use_llm_model.model_entity.extra_args,
                    remove_think=remove_think,
                )

                yield msg
                final_msg = msg

            pending_tool_calls = final_msg.tool_calls

            req_messages.append(final_msg)
