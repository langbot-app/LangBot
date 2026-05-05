"""Iterator Node - Dify-style iterator for processing array items"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('iterator')
class IteratorNode(WorkflowNode):
    """Iterator node - iterate over array items one by one"""

    type_name = "iterator"
    category = "control"
    icon = "🔄"
    name = "iterator"
    name_zh = "迭代器"
    name_en = "Iterator"
    description = "iterator"
    description_zh = "逐个遍历数组元素"
    description_en = "Iterate over array elements one by one"

    inputs: ClassVar[list[NodePort]] = [
        NodePort(name="items", type="array", description="Array to iterate over", required=True),
    ]
    outputs: ClassVar[list[NodePort]] = [
        NodePort(name="item", type="any", description="Current item"),
        NodePort(name="index", type="number", description="Current index"),
        NodePort(name="is_first", type="boolean", description="Whether this is the first item"),
        NodePort(name="is_last", type="boolean", description="Whether this is the last item"),
        NodePort(name="results", type="array", description="All iteration results"),
        NodePort(name="completed", type="boolean", description="Whether iteration completed"),
    ]
    config_schema: ClassVar[list[NodeConfig]] = [
        NodeConfig(
            name="max_iterations", type="integer", required=False, default=1000,
            description="Maximum iterations (safety limit)",
            label={"en_US": "Max Iterations", "zh_Hans": "最大迭代次数"},
        ),
    ]

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        items = inputs.get("items", [])
        if not isinstance(items, list):
            items = [items] if items else []

        max_iterations = self.get_config("max_iterations", 1000)
        items = items[:max_iterations]

        return {
            "item": items[0] if items else None,
            "index": 0,
            "is_first": True,
            "is_last": len(items) <= 1,
            "results": [],
            "completed": len(items) == 0,
            "_items": items,
        }
