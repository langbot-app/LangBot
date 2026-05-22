"""Parameter Extractor Node - extract structured parameters from text

Node metadata is loaded from: ../../templates/metadata/nodes/parameter_extractor.yaml
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

@workflow_node('parameter_extractor')
class ParameterExtractorNode(WorkflowNode):
    """Parameter extractor node - extract structured parameters from text"""

    category = 'process'
    icon: str = 'Variable'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Get input text
        input_text = inputs.get('input') or inputs.get('message') or inputs.get('content') or ''
        input_text = str(input_text) if input_text is not None else ''

        # Get configuration
        param_defs = self.get_config('parameters', [])
        model_id = self.get_config('model', '')
        system_prompt = self.get_config('system_prompt', '')

        if not input_text.strip():
            return {
                'parameters': {},
                'extraction_success': False,
                'error': 'Empty input',
            }

        if not param_defs:
            return {
                'parameters': {},
                'extraction_success': False,
                'error': 'No parameters configured',
            }

        # Build parameter schema for LLM prompt
        param_schema = []
        for param in param_defs:
            schema_item = {
                'name': param.get('name', ''),
                'type': param.get('type', 'string'),
                'description': param.get('description', ''),
                'required': param.get('required', False),
            }
            param_schema.append(schema_item)

        # Build extraction prompt
        if not system_prompt:
            system_prompt = (
                f'Extract the following parameters from the user\'s text as JSON. '
                f'Respond with ONLY a valid JSON object containing the extracted parameters.\n\n'
                f'Parameters to extract:\n'
                f'{json.dumps(param_schema, indent=2, ensure_ascii=False)}\n\n'
                f'Respond with a JSON object like: {{"param_name": "value", ...}}'
            )

        # Call LLM for extraction
        if self.ap and model_id:
            try:
                # Get model (same as llm_call.py)
                runtime_model = await self.ap.model_mgr.get_model_by_uuid(model_id)

                # Build messages
                from langbot_plugin.api.entities.builtin.provider.message import Message
                messages = []
                if system_prompt:
                    messages.append(Message(role='system', content=system_prompt))
                messages.append(Message(role='user', content=input_text))

                # Invoke LLM (same as llm_call.py)
                result_message = await runtime_model.provider.invoke_llm(
                    query=None,
                    model=runtime_model,
                    messages=messages,
                    funcs=None,
                    extra_args={},
                )

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

                response_text = response_text.strip()

                # Parse JSON response
                try:
                    extracted = json.loads(response_text)
                    return {
                        'parameters': extracted,
                        'extraction_success': True,
                        'raw_response': response_text[:500],
                    }
                except json.JSONDecodeError as e:
                    logger.error('ParameterExtractorNode JSON parse error: %s', e)
                    return {
                        'parameters': {},
                        'extraction_success': False,
                        'error': f'Failed to parse JSON: {e}',
                        'raw_response': response_text[:500],
                    }

            except Exception as e:
                logger.error('ParameterExtractorNode LLM error: %s', e, exc_info=True)
                return {
                    'parameters': {},
                    'extraction_success': False,
                    'error': f'LLM error: {e}',
                }
        else:
            return {
                'parameters': {},
                'extraction_success': False,
                'error': 'Missing model configuration',
            }
