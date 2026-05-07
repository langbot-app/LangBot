"""Dify Workflow Node - call Dify service API

Node metadata is loaded from: ../../templates/metadata/nodes/dify_workflow.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('dify_workflow')
class DifyWorkflowNode(WorkflowNode):
    """Dify workflow node - call Dify service API"""

    type_name = "dify_workflow"
    category = "integration"
    icon = "Bot"
    name = "dify_workflow"
    description = "dify_workflow"
    name_zh = "Dify 工作流"
    name_en = "Dify Workflow"
    description_zh = "调用 Dify 平台工作流"
    description_en = "Call a Dify platform workflow"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        base_url = self.get_config("base_url", "https://api.dify.ai/v1")
        api_key = self.get_config("api_key", "")
        app_type = self.get_config("app_type", "chat")
        query = inputs.get("query", "")
        conversation_id = inputs.get("conversation_id")

        return {
            "answer": "",
            "conversation_id": conversation_id,
            "success": False,
            "_debug": {
                "base_url": base_url,
                "api_key": api_key[:8] + "..." if api_key else "",
                "app_type": app_type,
                "query": query,
            },
        }
