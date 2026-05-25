"""N8n Workflow Node - call n8n workflow API

Node metadata is loaded from: ../../templates/metadata/nodes/n8n_workflow.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('n8n_workflow')
class N8nWorkflowNode(WorkflowNode):
    """n8n workflow node - call n8n workflow API"""

    category = 'integration'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        webhook_url = self.get_config('webhook_url', '')
        auth_type = self.get_config('auth_type', 'none')
        timeout = self.get_config('timeout', 120)
        payload = inputs.get('payload', {})

        return {
            'result': None,
            'success': False,
            '_debug': {
                'webhook_url': webhook_url,
                'auth_type': auth_type,
                'timeout': timeout,
                'payload': payload,
            },
        }
