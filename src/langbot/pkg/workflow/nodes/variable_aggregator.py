"""Variable Aggregator Node - aggregate variables from multiple branches

Node metadata is loaded from: ../../templates/metadata/nodes/variable_aggregator.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('variable_aggregator')
class VariableAggregatorNode(WorkflowNode):
    """Variable aggregator node - aggregate variables from multiple branches"""

    type_name = "variable_aggregator"
    category = "control"
    icon = "📊"
    name = "variable_aggregator"
    description = "variable_aggregator"
    name_zh = "变量聚合器"
    name_en = "Variable Aggregator"
    description_zh = "聚合多个分支的变量输出"
    description_en = "Aggregate variable outputs from multiple branches"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        variables = inputs.get("variables", {})
        mode = self.get_config("aggregation_mode", "merge")

        aggregated = {}

        if mode == "merge":
            if isinstance(variables, dict):
                aggregated.update(variables)
        elif mode == "override":
            if isinstance(variables, dict):
                aggregated = variables.copy()
        elif mode == "append":
            for key, value in (variables if isinstance(variables, dict) else {}).items():
                if key in aggregated and isinstance(aggregated[key], list):
                    aggregated[key].append(value)
                else:
                    aggregated[key] = [value]

        return {"aggregated": aggregated}
