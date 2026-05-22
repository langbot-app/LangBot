"""Send Message Node - send message to a target

Node metadata is loaded from: ../../templates/metadata/nodes/send_message.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

@workflow_node('send_message')
class SendMessageNode(WorkflowNode):
    """Send message node - send message to a target"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Get message content from inputs
        message = inputs.get('message') or inputs.get('content') or inputs.get('input') or ''
        message = str(message) if message is not None else ''

        # Get target configuration
        target_type = self.get_config('target_type', 'person')
        target_id = self.get_config('target_id', '')
        
        # If no target_id configured, use session_id from context
        if not target_id:
            target_id = f'{context.session_id or "unknown"}'

        if not message.strip():
            logger.warning('SendMessageNode has empty message')
            return {
                'status': 'failed',
                'error': 'Empty message',
                'message_preview': '',
            }

        # Send message if application instance is available
        send_success = False
        send_error = None
        if self.ap:
            try:
                from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

                message_chain = MessageChain([Plain(text=message)])
                await self.ap.platform_mgr.websocket_proxy_bot.adapter.send_message(
                    target_type=target_type,
                    target_id=target_id,
                    message=message_chain,
                )
                send_success = True
                logger.info('SendMessageNode sent message to %s:%s', target_type, target_id)
            except Exception as e:
                send_error = str(e)
                logger.error('SendMessageNode send failed: %s', e, exc_info=True)
        else:
            send_error = 'Missing application instance'
            logger.warning('SendMessageNode missing application instance')

        return {
            'status': 'sent' if send_success else 'failed',
            'message_preview': message[:200],
            'target_type': target_type,
            'target_id': target_id,
            'error': send_error,
        }
