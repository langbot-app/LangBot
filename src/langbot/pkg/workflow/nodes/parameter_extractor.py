"""Parameter Extractor Node - extract structured parameters from text

Node metadata is loaded from: ../../templates/metadata/nodes/parameter_extractor.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('parameter_extractor')
class ParameterExtractorNode(WorkflowNode):
    """Parameter extractor node - extract structured parameters from text"""

    type_name = "parameter_extractor"
    category = "process"
    icon: str = "📤"
    name = "parameter_extractor"
    description = "parameter_extractor"
    name_zh = "参数提取器"
    name_en = "Parameter Extractor"
    description_zh = "使用 AI 从文本中提取结构化参数"
    description_en = "Extract structured parameters from text using AI"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        text = inputs.get("text", "")
        param_defs = self.get_config("parameters", [])

        extracted = {}
        for param in param_defs:
            extracted[param.get("name", "")] = None

        return {"parameters": extracted, "extraction_success": False}
