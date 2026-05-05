"""Call Pipeline Node - invoke an existing pipeline

Node metadata is loaded from: ../../templates/metadata/nodes/call_pipeline.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('call_pipeline')
class CallPipelineNode(WorkflowNode):
    """Call pipeline node - invoke an existing pipeline"""

    type_name = "call_pipeline"
    category = "action"
    icon = "⚙️"
    name = "call_pipeline"
    description = "call_pipeline"
    name_zh = "调用 Pipeline"
    name_en = "Call Pipeline"
    description_zh = "调用现有的 Pipeline 进行处理"
    description_en = "Invoke an existing Pipeline for processing"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        query = inputs.get("query", "")
        pipeline_uuid = self.get_config("pipeline_uuid", "")

        return {"response": f"[Pipeline {pipeline_uuid} response for: {query[:50]}...]", "result": {}}
