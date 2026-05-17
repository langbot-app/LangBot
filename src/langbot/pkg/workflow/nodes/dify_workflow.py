"""Dify Workflow Node - call Dify service API

Node metadata is loaded from: ../../templates/metadata/nodes/dify_workflow.yaml
"""

from __future__ import annotations

from typing import Any

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('dify_workflow')
class DifyWorkflowNode(WorkflowNode):
    """Dify workflow node - call Dify service API"""

    category = 'integration'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        base_url = self.get_config('base_url', 'https://api.dify.ai/v1')
        api_key = self.get_config('api_key', '')
        app_type = self.get_config('app_type', 'chat')
        query = inputs.get('query', '')
        conversation_id = inputs.get('conversation_id')

        return {
            'answer': '',
            'conversation_id': conversation_id,
            'success': False,
            '_debug': {
                'base_url': base_url,
                'api_key': api_key[:8] + '...' if api_key else '',
                'app_type': app_type,
                'query': query,
            },
        }
