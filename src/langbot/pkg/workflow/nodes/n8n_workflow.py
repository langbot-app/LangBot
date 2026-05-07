"""N8n Workflow Node - call n8n workflow API

Node metadata is loaded from: ../../templates/metadata/nodes/n8n_workflow.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('n8n_workflow')
class N8nWorkflowNode(WorkflowNode):
    """n8n workflow node - call n8n workflow API"""

    type_name = "n8n_workflow"
    category = "integration"
    icon = "Workflow"
    name = "n8n_workflow"
    description = "n8n_workflow"
    name_zh = "n8n 工作流"
    name_en = "N8n Workflow"
    description_zh = "通过 webhook 调用 n8n 工作流"
    description_en = "Call an n8n workflow via webhook"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        webhook_url = self.get_config("webhook_url", "")
        auth_type = self.get_config("auth_type", "none")
        timeout = self.get_config("timeout", 120)
        payload = inputs.get("payload", {})

        return {
            "result": None,
            "success": False,
            "_debug": {
                "webhook_url": webhook_url,
                "auth_type": auth_type,
                "timeout": timeout,
                "payload": payload,
            },
        }
