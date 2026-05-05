"""Parallel Node - execute multiple branches simultaneously"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('parallel')
class ParallelNode(WorkflowNode):
    """Parallel node - execute multiple branches simultaneously"""

    type_name = "parallel"
    category = "control"
    icon = "⚡"
    name = "parallel"
    name_zh = "并行执行"
    name_en = "Parallel"
    description = "parallel"
    description_zh = "并行执行多个分支"
    description_en = "Execute multiple branches in parallel"

    inputs: ClassVar[list[NodePort]] = [
        NodePort(name="input", type="any", description="Input data for all branches", required=False),
    ]
    outputs: ClassVar[list[NodePort]] = [
        NodePort(name="results", type="object", description="Combined results from all branches"),
        NodePort(name="errors", type="array", description="Errors from branches (if any)"),
    ]
    config_schema: ClassVar[list[NodeConfig]] = [
        NodeConfig(
            name="wait_all", type="boolean", required=False, default=True,
            description="Wait for all branches to complete",
            label={"en_US": "Wait for All", "zh_Hans": "等待全部完成"},
        ),
        NodeConfig(
            name="fail_fast", type="boolean", required=False, default=False,
            description="Stop all branches if any fails",
            label={"en_US": "Fail Fast", "zh_Hans": "快速失败"},
        ),
    ]

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {
            "results": {},
            "errors": [],
        }
