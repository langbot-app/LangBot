"""Send Message Node - send message to a target

Node metadata is loaded from: ../../templates/metadata/nodes/send_message.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

from langbot.pkg.workflow.protocol.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node
from ..runtime import current_runtime

logger = logging.getLogger(__name__)


@workflow_node('send_message')
class SendMessageNode(WorkflowNode):
    """Send a message through the triggering bot to a person or group."""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        message = inputs.get('message') or inputs.get('content') or inputs.get('input') or ''
        message = str(message)
        if not message.strip():
            return {'status': 'failed', 'error': 'Empty message'}

        target_type = str(self.get_config('target_type', '') or '')
        target_id = str(inputs.get('target_id') or self.get_config('target_id', '') or '')
        runtime = current_runtime()
        chain = MessageChain([Plain(text=message)])

        if not target_id:
            # No explicit target: deliver to the conversation that triggered the workflow.
            await runtime.reply(chain)
            return {'status': 'sent', 'message_content': message, 'error': None}

        if target_type not in ('person', 'group'):
            raise ValueError('send_message target_type must be person or group')
        await runtime.send(target_type, target_id, chain)
        return {
            'status': 'sent',
            'message_content': message,
            'target_type': target_type,
            'target_id': target_id,
            'error': None,
        }
