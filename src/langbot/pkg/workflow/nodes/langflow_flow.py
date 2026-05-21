"""Langflow Flow Node - call Langflow API

Node metadata is loaded from: ../../templates/metadata/nodes/langflow_flow.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('langflow_flow')
class LangflowFlowNode(WorkflowNode):
    """Langflow flow node - call Langflow API"""

    category = 'integration'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        base_url = self.get_config('base_url', 'http://localhost:7860')
        api_key = self.get_config('api_key', '')
        flow_id = self.get_config('flow_id', '')
        input_value = inputs.get('input_value', '')

        return {
            'result': None,
            'success': False,
            '_debug': {
                'base_url': base_url,
                'api_key': api_key[:8] + '...' if api_key else '',
                'flow_id': flow_id,
                'input_value': input_value,
            },
        }
