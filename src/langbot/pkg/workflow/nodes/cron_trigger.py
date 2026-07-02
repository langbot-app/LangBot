"""Cron Trigger Node - triggers workflow on schedule

Node metadata is loaded from: ../../templates/metadata/nodes/cron_trigger.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('cron_trigger')
class CronTriggerNode(WorkflowNode):
    """Cron trigger node - triggers workflow on schedule"""

    category = 'trigger'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        from datetime import datetime

        return {
            'timestamp': datetime.now().isoformat(),
            'schedule': self.get_config('cron', ''),
            'context': context.trigger_data,
        }
