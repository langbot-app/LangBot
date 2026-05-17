"""Webhook Trigger Node - triggers workflow via HTTP request

Node metadata is loaded from: ../../templates/metadata/nodes/webhook_trigger.yaml
"""

from __future__ import annotations

from typing import Any

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('webhook_trigger')
class WebhookTriggerNode(WorkflowNode):
    """Webhook trigger node - triggers workflow via HTTP request"""

    category = 'trigger'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        trigger_data = context.trigger_data

        return {
            'body': trigger_data.get('body', {}),
            'headers': trigger_data.get('headers', {}),
            'query': trigger_data.get('query', {}),
            'method': trigger_data.get('method', 'POST'),
        }
