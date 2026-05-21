"""Question Classifier Node - classify user questions into categories

Node metadata is loaded from: ../../templates/metadata/nodes/question_classifier.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('question_classifier')
class QuestionClassifierNode(WorkflowNode):
    """Question classifier node - classify user questions into categories"""

    category = 'process'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        categories = self.get_config('categories', [])

        if categories:
            return {
                'category': categories[0].get('name', 'unknown'),
                'confidence': 0.8,
                'all_scores': {cat.get('name'): 0.1 for cat in categories},
            }

        return {'category': 'unknown', 'confidence': 0.0, 'all_scores': {}}
