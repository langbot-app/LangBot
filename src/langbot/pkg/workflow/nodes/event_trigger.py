"""Event Trigger Node - triggers workflow on system events

Node metadata is loaded from: ../../templates/metadata/nodes/event_trigger.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('event_trigger')
class EventTriggerNode(WorkflowNode):
    """Event trigger node - triggers workflow on system events"""

    category = 'trigger'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        from datetime import datetime

        trigger_data = context.trigger_data

        return {
            'event_type': trigger_data.get('event_type', ''),
            'event_data': trigger_data.get('event_data', {}),
            'timestamp': trigger_data.get('timestamp', datetime.now().isoformat()),
        }
