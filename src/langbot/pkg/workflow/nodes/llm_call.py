"""LLM Call Node - invoke large language model."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncGenerator

import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

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
        except Exception:
            pass

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
                    except Exception:
                        pass

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

    def _parse_tools_config(self, tools_config: Any) -> list[dict]:
        """Parse tools configuration from YAML config format."""
        if not tools_config:
            return []

        # If it's already a list, return as-is
        if isinstance(tools_config, list):
            return tools_config

        # If it's a string, try to parse as JSON
        if isinstance(tools_config, str):
            tools_config = tools_config.strip()
            if not tools_config:
                return []
            try:
                parsed = json.loads(tools_config)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                logger.warning(f'Failed to parse tools config as JSON: {tools_config}')
                return []

        return []

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

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        model_uuid = self.get_config('model', '')
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

        # Get tools config
        enable_tools = self.get_config('enable_tools', False)
        tools_config = self.get_config('tools', [])

        # Resolve prompts
        system_prompt = self._resolve_template(self.get_config('system_prompt') or '', inputs, context)
        user_prompt_template = self.get_config('user_prompt_template')
        if user_prompt_template is None:
            user_prompt_template = '{{input}}'
        user_prompt = self._resolve_template(user_prompt_template, inputs, context)

        # Build system prompt with format instructions
        system_prompt = self._build_system_prompt_with_format(system_prompt, output_format, json_schema)

        # Build messages
        messages: list[provider_message.Message] = []
        if system_prompt:
            messages.append(provider_message.Message(role='system', content=system_prompt))
        messages.append(provider_message.Message(role='user', content=user_prompt))

        # Get model
        runtime_model = await self.ap.model_mgr.get_model_by_uuid(model_uuid)

        # Build extra args from config
        extra_args: dict[str, Any] = {}
        temperature = self.get_config('temperature')
        if temperature is not None:
            extra_args['temperature'] = float(temperature)
        max_tokens = self.get_config('max_tokens', 0)
        if max_tokens and int(max_tokens) > 0:
            extra_args['max_tokens'] = int(max_tokens)

        # Build tools list if enabled
        funcs: list[resource_tool.LLMTool] | None = None
        if enable_tools and tools_config:
            try:
                tool_names = self._parse_tools_config(tools_config)
                if tool_names:
                    all_tools = await self.ap.tool_mgr.get_tools()
                    funcs = [t for t in all_tools if t.name in tool_names]
            except Exception as e:
                logger.warning(f'[LLM:{self.node_id}] Failed to load tools: {e}')
                funcs = None

        # Invoke LLM
        try:
            result_message = await runtime_model.provider.invoke_llm(
                query=None,
                model=runtime_model,
                messages=messages,
                funcs=funcs,
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
        usage = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }
        if hasattr(result_message, 'usage') and result_message.usage:
            u = result_message.usage
            usage = {
                'prompt_tokens': getattr(u, 'prompt_tokens', 0) or 0,
                'completion_tokens': getattr(u, 'completion_tokens', 0) or 0,
                'total_tokens': getattr(u, 'total_tokens', 0) or 0,
            }
        elif hasattr(result_message, 'token_usage') and result_message.token_usage:
            u = result_message.token_usage
            usage = {
                'prompt_tokens': getattr(u, 'prompt_tokens', 0) or 0,
                'completion_tokens': getattr(u, 'completion_tokens', 0) or 0,
                'total_tokens': getattr(u, 'total_tokens', 0) or 0,
            }

        # Build result
        result: dict[str, Any] = {
            'response': response_text,
            'usage': usage,
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
        model_uuid = self.get_config('model', '')
        if not model_uuid:
            raise ValueError('No model configured for LLM call node')

        if not self.ap:
            raise RuntimeError('Application instance not available - cannot call LLM')

        exception_handling = self.get_config('exception_handling', 'show-error')
        failure_hint = self.get_config('failure_hint', 'Request failed.')

        # Resolve prompts
        system_prompt = self._resolve_template(self.get_config('system_prompt') or '', inputs, context)
        user_prompt_template = self.get_config('user_prompt_template')
        if user_prompt_template is None:
            user_prompt_template = '{{input}}'
        user_prompt = self._resolve_template(user_prompt_template, inputs, context)

        # Build messages
        messages: list[provider_message.Message] = []
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
