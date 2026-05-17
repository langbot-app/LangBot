"""LLM Call Node - invoke large language model."""

from __future__ import annotations

import logging
import re
from typing import Any

import langbot_plugin.api.entities.builtin.provider.message as provider_message

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

@workflow_node('llm_call')
class LLMCallNode(WorkflowNode):
    """LLM call node - invoke large language model"""

    category = 'process'

    def _resolve_template(self, template: str, inputs: dict[str, Any], context: ExecutionContext) -> str:
        """Resolve {{variable}} placeholders in a template string."""

        def replacer(match: re.Match) -> str:
            expr = match.group(1).strip()
            # Try inputs first
            if expr in inputs:
                return str(inputs[expr])
            # Try context variables
            if expr.startswith('variables.'):
                var_name = expr[len('variables.') :]
                return str(context.variables.get(var_name, ''))
            # Try message context
            if expr.startswith('message.') and context.message_context:
                attr = expr[len('message.') :]
                return str(getattr(context.message_context, attr, ''))
            return match.group(0)  # leave unresolved

        return re.sub(r'\{\{([^}]+)\}\}', replacer, template)

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        model_uuid = self.get_config('model', '')
        if not model_uuid:
            raise ValueError('No model configured for LLM call node')

        if not self.ap:
            raise RuntimeError('Application instance not available — cannot call LLM')

        # Resolve prompts
        system_prompt = self._resolve_template(self.get_config('system_prompt', ''), inputs, context)
        user_prompt = self._resolve_template(self.get_config('user_prompt_template', '{{input}}'), inputs, context)

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

        # Invoke LLM
        logger.info(f'LLM call node {self.node_id}: invoking model {model_uuid}')
        result_message = await runtime_model.provider.invoke_llm(
            query=None,
            model=runtime_model,
            messages=messages,
            funcs=None,
            extra_args=extra_args,
        )

        # Extract response text
        response_text = ''
        if isinstance(result_message.content, str):
            response_text = result_message.content
        elif isinstance(result_message.content, list):
            # ContentElement list — concatenate text elements
            for elem in result_message.content:
                if hasattr(elem, 'text') and elem.text:
                    response_text += elem.text
                elif isinstance(elem, str):
                    response_text += elem

        # Extract usage info if available
        usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
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

        return {
            'response': response_text,
            'usage': usage,
        }
