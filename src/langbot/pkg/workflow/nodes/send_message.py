"""Send Message Node - send message to a target

Node metadata is loaded from: ../../templates/metadata/nodes/send_message.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('send_message')
class SendMessageNode(WorkflowNode):
    """Send message node - send message to a target"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {'status': 'sent', 'message_id': f'msg_{context.execution_id}'}
