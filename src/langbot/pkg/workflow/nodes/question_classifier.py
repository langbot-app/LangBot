"""Question Classifier Node - classify user questions into categories

Node metadata is loaded from: ../../templates/metadata/nodes/question_classifier.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

@workflow_node('question_classifier')
class QuestionClassifierNode(WorkflowNode):
    """Question classifier node - classify user questions into categories"""

    category = 'process'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Get input text
        input_text = inputs.get('input') or inputs.get('message') or inputs.get('content') or ''
        input_text = str(input_text) if input_text is not None else ''

        # Get configuration
        categories = self.get_config('categories', [])
        model_id = self.get_config('model', '')
        system_prompt = self.get_config('system_prompt', '')

        if not input_text.strip():
            return {
                'category': 'unknown',
                'confidence': 0.0,
                'all_scores': {},
                'error': 'Empty input',
            }

        if not categories:
            return {
                'category': 'unknown',
                'confidence': 0.0,
                'all_scores': {},
                'error': 'No categories configured',
            }

        # Build category list for LLM prompt
        category_names = [cat.get('name', '') for cat in categories if cat.get('name')]

        # Build classification prompt
        if not system_prompt:
            system_prompt = (
                f'You are a question classifier. Classify the user\'s question into one of these categories: '
                f'{", ".join(category_names)}. '
                f'Respond with ONLY the category name, nothing else.'
            )

        # Call LLM for classification
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

                # Find matching category
                matched_category = None
                for cat in categories:
                    if cat.get('name', '').lower() == response_text.lower():
                        matched_category = cat
                        break

                if matched_category:
                    return {
                        'category': matched_category['name'],
                        'confidence': 0.9,
                        'all_scores': {cat.get('name', ''): 0.1 for cat in categories},
                    }
                else:
                    # Default to first category if no match
                    return {
                        'category': category_names[0] if category_names else 'unknown',
                        'confidence': 0.5,
                        'all_scores': {cat.get('name', ''): 0.1 for cat in categories},
                    }

            except Exception as e:
                logger.error('QuestionClassifierNode LLM error: %s', e, exc_info=True)
                return {
                    'category': category_names[0] if category_names else 'unknown',
                    'confidence': 0.0,
                    'all_scores': {},
                    'error': f'LLM error: {e}',
                }
        else:
            return {
                'category': category_names[0] if category_names else 'unknown',
                'confidence': 0.0,
                'all_scores': {},
                'error': 'Missing model configuration',
            }
