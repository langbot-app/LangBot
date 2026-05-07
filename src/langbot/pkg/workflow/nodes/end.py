"""End Node - marks the end of workflow execution

Node metadata is loaded from: ../../templates/metadata/nodes/end.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('end')
class EndNode(WorkflowNode):
    """End node - marks the end of workflow execution"""

    type_name = "end"
    category = "action"
    icon = "🏁"
    name = "end"
    description = "end"
    name_zh = "结束"
    name_en = "End"
    description_zh = "结束工作流执行"
    description_en = "End the workflow execution"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        result = inputs.get("result")
        output_format = self.get_config("output_format", "passthrough")

        if output_format == "text":
            return {"output": str(result)}
        elif output_format == "json":
            import json
            try:
                return {"output": json.dumps(result, ensure_ascii=False)}
            except Exception:
                return {"output": str(result)}
        else:
            return {"output": result}
