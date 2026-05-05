"""Cron Trigger Node - triggers workflow on schedule

Node metadata is loaded from: ../../templates/metadata/nodes/cron_trigger.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('cron_trigger')
class CronTriggerNode(WorkflowNode):
    """Cron trigger node - triggers workflow on schedule"""

    type_name = "cron_trigger"
    category = "trigger"
    icon = "⏰"
    name = "cron_trigger"
    description = "cron_trigger"
    name_zh = "定时触发"
    name_en = "Scheduled Trigger"
    description_zh = "按定时计划触发工作流"
    description_en = "Trigger workflow on a scheduled time"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        from datetime import datetime

        return {
            "timestamp": datetime.now().isoformat(),
            "schedule": self.get_config("cron", ""),
            "context": context.trigger_data,
        }
