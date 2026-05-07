"""Wait Node - pause execution for a duration

Node metadata is loaded from: ../../templates/metadata/nodes/wait.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('wait')
class WaitNode(WorkflowNode):
    """Wait node - pause execution for a duration"""

    type_name = "wait"
    category = "control"
    icon = "⏳"
    name = "wait"
    description = "wait"
    name_zh = "等待"
    name_en = "Wait"
    description_zh = "暂停工作流执行指定时间"
    description_en = "Pause workflow execution for a specified duration"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        import asyncio

        duration = self.get_config("duration", 1)
        duration_type = self.get_config("duration_type", "seconds")

        if duration_type == "minutes":
            duration *= 60
        elif duration_type == "hours":
            duration *= 3600

        await asyncio.sleep(duration)

        return {"output": inputs.get("input")}
