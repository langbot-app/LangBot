"""Loop Node - iterate over items"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('loop')
class LoopNode(WorkflowNode):
    """Loop node - iterate over items"""

    type_name = "loop"
    category = "control"
    icon = "🔁"
    name = "loop"
    name_zh = "循环"
    name_en = "Loop"
    description = "loop"
    description_zh = "遍历项目或重复直到满足条件"
    description_en = "Iterate over items or repeat until condition"

    inputs: ClassVar[list[NodePort]] = [
        NodePort(name="items", type="array", description="Items to iterate over", required=False),
    ]
    outputs: ClassVar[list[NodePort]] = [
        NodePort(name="item", type="any", description="Current item in iteration"),
        NodePort(name="index", type="number", description="Current iteration index"),
        NodePort(name="results", type="array", description="All iteration results"),
        NodePort(name="completed", type="boolean", description="Whether loop completed"),
    ]
    config_schema: ClassVar[list[NodeConfig]] = [
        NodeConfig(
            name="loop_type", type="select", required=True, default="foreach",
            description="Type of loop",
            label={"en_US": "Loop Type", "zh_Hans": "循环类型"},
            options=["foreach", "while", "count"],
        ),
        NodeConfig(
            name="max_iterations", type="integer", required=False, default=100,
            description="Maximum iterations (safety limit)",
            label={"en_US": "Max Iterations", "zh_Hans": "最大迭代次数"},
        ),
    ]

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        items = inputs.get("items", [])
        if not isinstance(items, list):
            items = [items] if items else []

        max_iterations = self.get_config("max_iterations", 100)
        items = items[:max_iterations]

        return {
            "item": items[0] if items else None,
            "index": 0,
            "results": [],
            "completed": len(items) == 0,
            "_items": items,
        }
