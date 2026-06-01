"""LLM Call Node - invoke large language model with Agent capabilities.

Supports:
- Primary model with fallback models
- Knowledge base retrieval with reranking
- Max round context control
- Streaming output
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, AsyncGenerator

import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.rag.context as rag_context

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node
from .. import monitoring_helper

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for CoT content removal (performance optimization)
_THINK_PATTERNS = [
    re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<thought>.*?</thought>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<reasoning>.*?</reasoning>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<\u601d\u8003>.*?</\u601d\u8003>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<\u63a8\u7406>.*?</\u63a8\u7406>', re.DOTALL | re.IGNORECASE),
]

# Template variable regex
_TEMPLATE_VAR_RE = re.compile(r'\{\{([^}]+)\}\}')


@workflow_node('llm_call')
class LLMCallNode(WorkflowNode):
    """LLM call node - invoke large language model"""

    category = 'process'

    def _resolve_template(self, template: str, inputs: dict[str, Any], context: ExecutionContext) -> str:
        """Resolve {{variable}} placeholders in a template string."""
        if not template:
            return ''

        unresolved_vars = []

        def replacer(match: re.Match) -> str:
            expr = match.group(1).strip()
            # Try inputs first
            if expr in inputs:
                return str(inputs[expr])
            # Try context variables
            if expr.startswith('variables.'):
                var_name = expr[len('variables.'):]
                return str(context.variables.get(var_name, ''))
            # Try message context
            if expr.startswith('message.') and context.message_context:
                attr = expr[len('message.'):]
                return str(getattr(context.message_context, attr, ''))
            unresolved_vars.append(expr)
            return match.group(0)  # leave unresolved

        result = _TEMPLATE_VAR_RE.sub(replacer, template)

        # Log warning for unresolved variables
        if unresolved_vars:
            logger.warning(
                f'LLM call node {self.node_id}: unresolved template variables: {unresolved_vars}'
            )

        return result

    def _remove_think_content(self, text: str) -> str:
        """Remove CoT (Chain of Thought) thinking content from response."""
        if not text:
            return text

        result = text
        for pattern in _THINK_PATTERNS:
            result = pattern.sub('', result)

        return result.strip()

    def _apply_content_filter(self, text: str) -> tuple[str, bool, str]:
        """Apply content safety filter to text.

        Returns:
            (filtered_text, is_blocked, user_notice)
        """
        if not text or not self.ap:
            return text, False, ''

        # Check if content filter is enabled
        safety_config = getattr(self.ap, 'pipeline_cfg', None)
        if not safety_config:
            return text, False, ''

        # Check sensitive words
        sensitive_words = []
        try:
            if hasattr(self.ap, 'sensitive_meta') and hasattr(self.ap.sensitive_meta, 'data'):
                sensitive_words = self.ap.sensitive_meta.data.get('words', [])
        except Exception as e:
            logger.warning("Failed to load sensitive words from sensitive_meta: %s", e)
            sensitive_words = []

        if not sensitive_words:
            return text, False, ''

        found = False
        filtered_text = text
        for word in sensitive_words:
            try:
                matches = re.findall(word, filtered_text, re.IGNORECASE)
                if matches:
                    found = True
                    mask_word = ''
                    mask = '*'
                    try:
                        if hasattr(self.ap, 'sensitive_meta') and hasattr(self.ap.sensitive_meta, 'data'):
                            mask_word = self.ap.sensitive_meta.data.get('mask_word', '')
                            mask = self.ap.sensitive_meta.data.get('mask', '*')
                    except Exception as e:
                        # Keep default mask settings when sensitive metadata is unavailable or malformed.
                        logger.debug(
                            f'LLM call node {self.node_id}: failed to read sensitive mask config, using defaults: {e}'
                        )

                    for m in matches:
                        if mask_word:
                            filtered_text = filtered_text.replace(m, mask_word)
                        else:
                            filtered_text = filtered_text.replace(m, mask * len(m))
            except re.error:
                # Invalid regex pattern, skip
                continue

        if found:
            return filtered_text, False, '消息中存在不合适的内容, 请修改'

        return text, False, ''

    # RAG combined prompt template (same as localagent.py)
    RAG_COMBINED_PROMPT_TEMPLATE = """
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

    def _build_system_prompt_with_format(self, base_prompt: str, output_format: str, json_schema: str) -> str:
        """Build system prompt with output format instructions."""
        prompt = base_prompt

        if output_format == 'json':
            prompt += '\n\nPlease respond in valid JSON format.'
            if json_schema:
                prompt += f'\nFollow this JSON schema:\n{json_schema}'
        elif output_format == 'markdown':
            prompt += '\n\nPlease respond in Markdown format.'

        return prompt

    def _build_messages_from_prompt_array(
        self,
        prompt_array: list[dict],
        inputs: dict[str, Any],
        context: ExecutionContext,
        output_format: str,
        json_schema: str,
    ) -> list[provider_message.Message]:
        """Build messages list from prompt array (same format as pipeline).
        
        Each item in prompt_array is {role: str, content: str}.
        Resolves template variables in content.
        """
        messages: list[provider_message.Message] = []
        
        for item in prompt_array:
            role = item.get('role', 'user')
            content = item.get('content', '')
            
            # Resolve template variables in content
            resolved_content = self._resolve_template(content, inputs, context)
            
            # Apply format instructions to system prompt
            if role == 'system':
                resolved_content = self._build_system_prompt_with_format(
                    resolved_content, output_format, json_schema
                )
            
            messages.append(provider_message.Message(role=role, content=resolved_content))
        
        return messages

    async def _get_model_candidates(self, model_uuid: str, fallback_models: list) -> list:
        """Build ordered list of models to try: primary model + fallback models."""
        candidates = []

        # Primary model
        if model_uuid:
            try:
                primary = await self.ap.model_mgr.get_model_by_uuid(model_uuid)
                candidates.append(primary)
            except ValueError:
                logger.warning(f'[LLM:{self.node_id}] Primary model {model_uuid} not found')

        # Fallback models
        for fb_uuid in fallback_models:
            try:
                fb_model = await self.ap.model_mgr.get_model_by_uuid(fb_uuid)
                candidates.append(fb_model)
            except ValueError:
                logger.warning(f'[LLM:{self.node_id}] Fallback model {fb_uuid} not found, skipping')

        return candidates

    async def _invoke_with_fallback(
        self,
        candidates: list,
        messages: list,
        funcs: list | None,
        extra_args: dict,
    ) -> tuple[Any, Any]:
        """Try non-streaming invocation with sequential fallback. Returns (message, model_used)."""
        last_error = None
        for model in candidates:
            try:
                msg = await model.provider.invoke_llm(
                    query=None,
                    model=model,
                    messages=messages,
                    funcs=funcs if model.model_entity.abilities.__contains__('func_call') else [],
                    extra_args=extra_args,
                )
                return msg, model
            except Exception as e:
                last_error = e
                logger.warning(f'[LLM:{self.node_id}] Model {model.model_entity.name} failed: {e}, trying next...')
        raise last_error or RuntimeError('No model candidates available')

    async def _retrieve_knowledge(
        self,
        user_message_text: str,
        knowledge_bases: list[str],
        rerank_model_uuid: str,
        rerank_top_k: int,
    ) -> str:
        """Retrieve from knowledge bases and optionally rerank results.
        
        Returns the enhanced user message text with RAG context, or original text if no results.
        """
        if not knowledge_bases or not user_message_text:
            return user_message_text

        all_results: list[rag_context.RetrievalResultEntry] = []

        # Retrieve from each knowledge base
        for kb_uuid in knowledge_bases:
            try:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
                if not kb:
                    logger.warning(f'[LLM:{self.node_id}] Knowledge base {kb_uuid} not found, skipping')
                    continue

                result = await kb.retrieve(user_message_text, settings={})
                if result:
                    all_results.extend(result)
            except Exception as e:
                logger.warning(f'[LLM:{self.node_id}] Failed to retrieve from KB {kb_uuid}: {e}')

        # Rerank step: re-score results using a rerank model if configured
        if all_results and rerank_model_uuid:
            try:
                rerank_model = await self.ap.model_mgr.get_rerank_model_by_uuid(rerank_model_uuid)
                
                doc_texts = []
                for entry in all_results:
                    text = ' '.join(c.text for c in entry.content if c.type == 'text' and c.text)
                    doc_texts.append(text)

                doc_texts_capped = doc_texts[:64]  # Cap for reranker input
                scores = await rerank_model.provider.invoke_rerank(
                    model=rerank_model,
                    query=user_message_text,
                    documents=doc_texts_capped,
                )

                scored = sorted(scores, key=lambda x: x.get('relevance_score', 0), reverse=True)
                top_indices = [s['index'] for s in scored[:rerank_top_k] if s['index'] < len(all_results)]
                all_results = [all_results[i] for i in top_indices]

                logger.info(
                    f'[LLM:{self.node_id}] Rerank complete: {len(doc_texts)} docs -> top {len(all_results)} kept (top_k={rerank_top_k})'
                )
            except ValueError:
                logger.warning(f'[LLM:{self.node_id}] Rerank model {rerank_model_uuid} not found, skipping rerank')
            except Exception as e:
                logger.warning(f'[LLM:{self.node_id}] Rerank failed, using original order: {e}')

        # Build RAG context text
        if all_results:
            texts = []
            idx = 1
            for entry in all_results:
                for content in entry.content:
                    if content.type == 'text' and content.text is not None:
                        texts.append(f'[{idx}] {content.text}')
                        idx += 1
            rag_context_text = '\n\n'.join(texts)
            return self.RAG_COMBINED_PROMPT_TEMPLATE.format(
                rag_context=rag_context_text,
                user_message=user_message_text,
            )

        return user_message_text

    def _build_messages_with_history(
        self,
        system_prompt: str,
        user_message_text: str,
        context: ExecutionContext,
        max_round: int,
    ) -> list[provider_message.Message]:
        """Build messages list with conversation history up to max_round."""
        messages: list[provider_message.Message] = []
        
        # Add system prompt
        if system_prompt:
            messages.append(provider_message.Message(role='system', content=system_prompt))

        # Get conversation history from context
        conversation_history = context.variables.get('_conversation_history', [])
        
        # Apply max_round limit (each round = 1 user + 1 assistant message)
        if max_round > 0 and conversation_history:
            # Keep only the last max_round * 2 messages (user + assistant pairs)
            max_messages = max_round * 2
            if len(conversation_history) > max_messages:
                conversation_history = conversation_history[-max_messages:]

        # Add conversation history
        for msg in conversation_history:
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                messages.append(provider_message.Message(role=role, content=content))
            elif hasattr(msg, 'role') and hasattr(msg, 'content'):
                messages.append(provider_message.Message(role=msg.role, content=msg.content))

        # Add current user message
        messages.append(provider_message.Message(role='user', content=user_message_text))

        return messages

    def _save_to_conversation_history(
        self,
        context: ExecutionContext,
        user_message_text: str,
        response_text: str,
        max_round: int,
    ) -> None:
        """Save the exchange to conversation history."""
        if max_round <= 0:
            return

        history = context.variables.get('_conversation_history', [])
        history.append({'role': 'user', 'content': user_message_text})
        history.append({'role': 'assistant', 'content': response_text})

        # Enforce max_round limit
        max_messages = max_round * 2
        if len(history) > max_messages:
            history = history[-max_messages:]

        context.variables['_conversation_history'] = history

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Support both new model_config format and legacy model + fallback_models format
        model_config = self.get_config('model_config', None)
        if model_config and isinstance(model_config, dict):
            # New format: {primary: uuid, fallbacks: [uuid1, uuid2, ...]}
            model_uuid = model_config.get('primary', '')
            fallback_models = model_config.get('fallbacks', [])
        else:
            # Legacy format: separate model and fallback_models
            model_uuid = self.get_config('model', '')
            fallback_models = self.get_config('fallback_models', [])
        
        if not model_uuid:
            raise ValueError('No model configured for LLM call node')

        if not self.ap:
            raise RuntimeError('Application instance not available - cannot call LLM')

        # Get error handling config
        exception_handling = self.get_config('exception_handling', 'show-error')
        failure_hint = self.get_config('failure_hint', 'Request failed.')
        track_function_calls = self.get_config('track_function_calls', False)

        # Get output format and json_schema config
        output_format = self.get_config('output_format', 'text')
        json_schema = self.get_config('json_schema', '')

        # Agent config: knowledge bases, rerank, max_round
        # (fallback_models already resolved above from model_config or fallback_models)
        knowledge_bases = self.get_config('knowledge_bases', [])
        rerank_model = self.get_config('rerank_model', '')
        rerank_top_k = self.get_config('rerank_top_k', 5)
        max_round = self.get_config('max_round', 10)

        # Resolve prompts - support both new prompt array format and legacy format
        prompt_array = self.get_config('prompt')
        user_prompt = ''  # Initialize for later use in _save_to_conversation_history
        
        if prompt_array and isinstance(prompt_array, list):
            # New format: prompt array like pipeline
            messages = self._build_messages_from_prompt_array(
                prompt_array, inputs, context, output_format, json_schema
            )
            
            # Get user input text for knowledge retrieval
            user_input = inputs.get('input', '')
            
            # Knowledge retrieval: enhance user input with RAG context
            user_input = await self._retrieve_knowledge(
                user_message_text=user_input,
                knowledge_bases=knowledge_bases,
                rerank_model_uuid=rerank_model,
                rerank_top_k=rerank_top_k,
            )
            
            # Track user_prompt for conversation history
            user_prompt = user_input
            
            # Add user input as last message
            if user_input:
                messages.append(provider_message.Message(role='user', content=user_input))
            
            # Apply max_round to conversation history
            conversation_history = context.variables.get('_conversation_history', [])
            if max_round > 0 and conversation_history:
                max_messages = max_round * 2
                if len(conversation_history) > max_messages:
                    conversation_history = conversation_history[-max_messages:]
                # Insert conversation history before user input
                history_messages = []
                for msg in conversation_history:
                    if isinstance(msg, dict):
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')
                        history_messages.append(provider_message.Message(role=role, content=content))
                    elif hasattr(msg, 'role') and hasattr(msg, 'content'):
                        history_messages.append(provider_message.Message(role=msg.role, content=msg.content))
                # Insert history before user message
                if history_messages and len(messages) > 0:
                    messages = messages[:-1] + history_messages + [messages[-1]]
        else:
            # Legacy format: separate system_prompt and user_prompt_template
            system_prompt = self._resolve_template(self.get_config('system_prompt') or '', inputs, context)
            user_prompt_template = self.get_config('user_prompt_template')
            if user_prompt_template is None:
                user_prompt_template = '{{input}}'
            user_prompt = self._resolve_template(user_prompt_template, inputs, context)

            # Build system prompt with format instructions
            system_prompt = self._build_system_prompt_with_format(system_prompt, output_format, json_schema)

            # Knowledge retrieval: enhance user prompt with RAG context
            user_prompt = await self._retrieve_knowledge(
                user_message_text=user_prompt,
                knowledge_bases=knowledge_bases,
                rerank_model_uuid=rerank_model,
                rerank_top_k=rerank_top_k,
            )

            # Build messages with conversation history
            messages = self._build_messages_with_history(
                system_prompt=system_prompt,
                user_message_text=user_prompt,
                context=context,
                max_round=max_round,
            )

        # Get model candidates (primary + fallbacks)
        candidates = await self._get_model_candidates(model_uuid, fallback_models)
        if not candidates:
            raise ValueError('No valid model candidates available')

        # Build extra args from config
        extra_args: dict[str, Any] = {}
        temperature = self.get_config('temperature')
        if temperature is not None:
            extra_args['temperature'] = float(temperature)
        max_tokens = self.get_config('max_tokens', 0)
        if max_tokens and int(max_tokens) > 0:
            extra_args['max_tokens'] = int(max_tokens)

        # Track start time for duration calculation
        self._llm_start_time = time.time()

        # Invoke LLM with fallback
        try:
            result_message, used_model = await self._invoke_with_fallback(
                candidates=candidates,
                messages=messages,
                funcs=None,
                extra_args=extra_args,
            )
        except Exception as e:
            logger.warning(f'[LLM:{self.node_id}] LLM call failed: {e}')

            # Handle based on exception handling strategy
            if exception_handling == 'show-error':
                raise
            elif exception_handling == 'show-hint':
                return {
                    'response': failure_hint,
                    'usage': {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                    },
                    'error': str(e),
                    'error_hint_shown': True,
                }
            else:  # hide
                return {
                    'response': '',
                    'usage': {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                    },
                    'error': str(e),
                }

        # Extract response text
        response_text = ''
        if isinstance(result_message.content, str):
            response_text = result_message.content
        elif isinstance(result_message.content, list):
            for elem in result_message.content:
                if hasattr(elem, 'text') and elem.text:
                    response_text += elem.text
                elif isinstance(elem, str):
                    response_text += elem

        # Remove CoT content (always remove to avoid leaking internal reasoning)
        response_text = self._remove_think_content(response_text)

        # Initialize usage default
        usage = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }

        # Apply content safety filter
        response_text, is_blocked, filter_notice = self._apply_content_filter(response_text)
        if is_blocked:
            logger.warning(f'[LLM:{self.node_id}] Response blocked by content filter: {filter_notice}')
            return {
                'response': filter_notice,
                'usage': usage,
                'blocked_by_filter': True,
            }

        # Extract usage info
        if hasattr(result_message, 'usage') and result_message.usage:
            u = result_message.usage
            # Handle both object and dict usage
            if isinstance(u, dict):
                usage = {
                    'prompt_tokens': u.get('prompt_tokens', 0) or 0,
                    'completion_tokens': u.get('completion_tokens', 0) or 0,
                    'total_tokens': u.get('total_tokens', 0) or 0,
                }
            else:
                usage = {
                    'prompt_tokens': getattr(u, 'prompt_tokens', 0) or 0,
                    'completion_tokens': getattr(u, 'completion_tokens', 0) or 0,
                    'total_tokens': getattr(u, 'total_tokens', 0) or 0,
                }
        elif hasattr(result_message, 'token_usage') and result_message.token_usage:
            u = result_message.token_usage
            # Handle both object and dict token_usage
            if isinstance(u, dict):
                usage = {
                    'prompt_tokens': u.get('prompt_tokens', 0) or 0,
                    'completion_tokens': u.get('completion_tokens', 0) or 0,
                    'total_tokens': u.get('total_tokens', 0) or 0,
                }
            else:
                usage = {
                    'prompt_tokens': getattr(u, 'prompt_tokens', 0) or 0,
                    'completion_tokens': getattr(u, 'completion_tokens', 0) or 0,
                    'total_tokens': getattr(u, 'total_tokens', 0) or 0,
                }

        # Log successful response (matching Pipeline's cut_str behavior)
        def _cut_str(s: str) -> str:
            s0 = s.split('\n')[0]
            if len(s0) > 20 or '\n' in s:
                s0 = s0[:20] + '...'
            return s0
        logger.info(f'[LLM:{self.node_id}] Response: {_cut_str(response_text)}')

        # Record LLM call log only (response log is redundant)
        try:
            if self.ap and context.query:
                workflow_id = context.workflow_id or ''
                workflow_name = context.variables.get('_workflow_name', 'Workflow')
                bot_name = context.variables.get('_bot_name', 'Workflow')
                node_name = self.get_config('name', self.node_id)
                model_name = used_model.model_entity.name if used_model else 'unknown'
                
                # Calculate duration
                duration_ms = 0
                if hasattr(self, '_llm_start_time'):
                    duration_ms = int((time.time() - self._llm_start_time) * 1000)
                
                # Get message_id for LLM call association
                message_id = context.variables.get('_monitoring_message_id')
                
                # Record LLM call log with message_id association
                await monitoring_helper.WorkflowMonitoringHelper.record_llm_call_log(
                    ap=self.ap,
                    query=context.query,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    node_name=node_name,
                    model_name=model_name,
                    input_tokens=usage.get('prompt_tokens', 0),
                    output_tokens=usage.get('completion_tokens', 0),
                    duration_ms=duration_ms,
                    status='success',
                    bot_name=bot_name,
                    context_vars=context.variables,
                    message_id=message_id,
                )
        except Exception as e:
            logger.warning(f'[LLM:{self.node_id}] Failed to record LLM logs: {e}')

        # Save to conversation history
        self._save_to_conversation_history(
            context=context,
            user_message_text=user_prompt,
            response_text=response_text,
            max_round=max_round,
        )

        # Build result
        result: dict[str, Any] = {
            'response': response_text,
            'usage': usage,
            'model_used': used_model.model_entity.name if used_model else None,
            'model_uuid': used_model.model_entity.uuid if used_model else None,
        }

        # Parse JSON output if format is json
        if output_format == 'json' and response_text:
            try:
                result['parsed'] = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f'[LLM:{self.node_id}] Failed to parse JSON: {e}')
                result['parsed'] = None
                result['parse_error'] = str(e)

        # Add function call tracking info if configured
        if track_function_calls:
            result['function_calls'] = []

        return result

    async def execute_stream(
        self, inputs: dict[str, Any], context: ExecutionContext
    ) -> AsyncGenerator[str, None]:
        """Execute the LLM call with streaming output.

        Yields chunks of response text as they arrive.
        Falls back to non-streaming if streaming is not available.
        """
        # Support both new model_config format and legacy model + fallback_models format
        model_config = self.get_config('model_config', None)
        if model_config and isinstance(model_config, dict):
            model_uuid = model_config.get('primary', '')
        else:
            model_uuid = self.get_config('model', '')
        
        if not model_uuid:
            raise ValueError('No model configured for LLM call node')

        if not self.ap:
            raise RuntimeError('Application instance not available - cannot call LLM')

        exception_handling = self.get_config('exception_handling', 'show-error')
        failure_hint = self.get_config('failure_hint', 'Request failed.')

        # Resolve prompts - support both new prompt array format and legacy format
        prompt_array = self.get_config('prompt')
        if prompt_array and isinstance(prompt_array, list):
            # New format: prompt array like pipeline
            messages = self._build_messages_from_prompt_array(
                prompt_array, inputs, context, 'text', ''  # No format instructions for streaming
            )
            
            # Add user input
            user_input = inputs.get('input', '')
            if user_input:
                messages.append(provider_message.Message(role='user', content=user_input))
        else:
            # Legacy format
            system_prompt = self._resolve_template(self.get_config('system_prompt') or '', inputs, context)
            user_prompt_template = self.get_config('user_prompt_template')
            if user_prompt_template is None:
                user_prompt_template = '{{input}}'
            user_prompt = self._resolve_template(user_prompt_template, inputs, context)

            # Build messages
            messages = []
            if system_prompt:
                messages.append(provider_message.Message(role='system', content=system_prompt))
            messages.append(provider_message.Message(role='user', content=user_prompt))

        # Get model
        runtime_model = await self.ap.model_mgr.get_model_by_uuid(model_uuid)

        # Build extra args
        extra_args: dict[str, Any] = {}
        temperature = self.get_config('temperature')
        if temperature is not None:
            extra_args['temperature'] = float(temperature)
        max_tokens = self.get_config('max_tokens', 0)
        if max_tokens and int(max_tokens) > 0:
            extra_args['max_tokens'] = int(max_tokens)

        logger.info(f'[LLM:{self.node_id}] Streaming model {model_uuid}')

        try:
            # Try streaming first
            stream = runtime_model.provider.invoke_llm_stream(
                query=None,
                model=runtime_model,
                messages=messages,
                funcs=None,
                extra_args=extra_args,
            )

            full_response = ''
            in_think_block = False
            async for chunk in stream:
                chunk_text = ''
                if hasattr(chunk, 'content'):
                    if isinstance(chunk.content, str):
                        chunk_text = chunk.content
                    elif isinstance(chunk.content, list):
                        for elem in chunk.content:
                            if hasattr(elem, 'text') and elem.text:
                                chunk_text += elem.text
                            elif isinstance(elem, str):
                                chunk_text += elem

                if chunk_text:
                    # Filter <think> blocks in streaming mode
                    if '<think>' in chunk_text or '<thought>' in chunk_text:
                        in_think_block = True
                    if in_think_block:
                        if '</think>' in chunk_text or '</thought>' in chunk_text:
                            in_think_block = False
                            chunk_text = chunk_text.split('</think>')[-1].split('</thought>')[-1]
                        else:
                            chunk_text = ''
                    
                    if chunk_text:
                        full_response += chunk_text
                        yield chunk_text

            # Store in context for downstream nodes
            context.variables['_last_llm_response'] = full_response

        except Exception as e:
            logger.warning(f'[LLM:{self.node_id}] Streaming failed, falling back - {e}')
            # Fallback to non-streaming
            try:
                result_message = await runtime_model.provider.invoke_llm(
                    query=None,
                    model=runtime_model,
                    messages=messages,
                    funcs=None,
                    extra_args=extra_args,
                )
                response_text = self._extract_response_text(result_message)
                # Always remove <think> content in fallback
                response_text = self._remove_think_content(response_text)
                yield response_text
                context.variables['_last_llm_response'] = response_text
            except Exception as e2:
                logger.error(f'[LLM:{self.node_id}] Fallback also failed - {e2}')
                if exception_handling == 'show-hint':
                    yield failure_hint
                elif exception_handling != 'hide':
                    raise

    def _extract_response_text(self, result_message: provider_message.Message) -> str:
        """Extract response text from LLM result message."""
        response_text = ''
        if isinstance(result_message.content, str):
            response_text = result_message.content
        elif isinstance(result_message.content, list):
            for elem in result_message.content:
                if hasattr(elem, 'text') and elem.text:
                    response_text += elem.text
                elif isinstance(elem, str):
                    response_text += elem
        return response_text
