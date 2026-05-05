"""Langflow Flow Node - call Langflow API

Node metadata is loaded from: ../../templates/metadata/nodes/langflow_flow.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('langflow_flow')
class LangflowFlowNode(WorkflowNode):
    """Langflow flow node - call Langflow API"""

    type_name = "langflow_flow"
    category = "integration"
    icon = "GitBranch"
    name = "langflow_flow"
    description = "langflow_flow"
    name_zh = "Langflow 流程"
    name_en = "Langflow Flow"
    description_zh = "调用 Langflow 流程"
    description_en = "Call a Langflow flow"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        base_url = self.get_config("base_url", "http://localhost:7860")
        api_key = self.get_config("api_key", "")
        flow_id = self.get_config("flow_id", "")
        input_value = inputs.get("input_value", "")

        return {
            "result": None,
            "success": False,
            "_debug": {
                "base_url": base_url,
                "api_key": api_key[:8] + "..." if api_key else "",
                "flow_id": flow_id,
                "input_value": input_value,
            },
        }
