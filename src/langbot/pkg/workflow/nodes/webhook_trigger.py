"""Webhook Trigger Node - triggers workflow via HTTP request

Node metadata is loaded from: ../../templates/metadata/nodes/webhook_trigger.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('webhook_trigger')
class WebhookTriggerNode(WorkflowNode):
    """Webhook trigger node - triggers workflow via HTTP request"""

    category = 'trigger'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Safe access to trigger_data which may be None
        trigger_data = context.trigger_data or {}

        # Filter sensitive headers (Authorization, Cookie, etc.)
        headers = trigger_data.get('headers', {})
        safe_headers = {k: v for k, v in headers.items()
                       if k.lower() not in ('authorization', 'cookie', 'x-api-key', 'x-secret')}

        return {
            'body': trigger_data.get('body', {}),
            'headers': safe_headers,
            'query': trigger_data.get('query', {}),
            'method': trigger_data.get('method', 'POST'),
        }
