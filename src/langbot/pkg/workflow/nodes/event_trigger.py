"""Event Trigger Node - triggers workflow on system events

Node metadata is loaded from: ../../templates/metadata/nodes/event_trigger.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('event_trigger')
class EventTriggerNode(WorkflowNode):
    """Event trigger node - triggers workflow on system events"""

    type_name = "event_trigger"
    category = "trigger"
    icon = "📡"
    name = "event_trigger"
    description = "event_trigger"
    name_zh = "事件触发"
    name_en = "Event Trigger"
    description_zh = "当系统事件发生时触发工作流"
    description_en = "Trigger workflow when a system event occurs"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        from datetime import datetime

        trigger_data = context.trigger_data

        return {
            "event_type": trigger_data.get("event_type", ""),
            "event_data": trigger_data.get("event_data", {}),
            "timestamp": trigger_data.get("timestamp", datetime.now().isoformat()),
        }
