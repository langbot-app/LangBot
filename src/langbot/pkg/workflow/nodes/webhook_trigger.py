"""Webhook Trigger Node - triggers workflow via HTTP request

Node metadata is loaded from: ../../templates/metadata/nodes/webhook_trigger.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('webhook_trigger')
class WebhookTriggerNode(WorkflowNode):
    """Webhook trigger node - triggers workflow via HTTP request"""

    type_name = "webhook_trigger"
    category = "trigger"
    icon = "🌐"
    name = "webhook_trigger"
    description = "webhook_trigger"
    name_zh = "Webhook 触发"
    name_en = "Webhook Trigger"
    description_zh = "通过 HTTP 请求触发工作流"
    description_en = "Trigger workflow via HTTP webhook"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        trigger_data = context.trigger_data

        return {
            "body": trigger_data.get("body", {}),
            "headers": trigger_data.get("headers", {}),
            "query": trigger_data.get("query", {}),
            "method": trigger_data.get("method", "POST"),
        }
