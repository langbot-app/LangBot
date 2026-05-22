"""Reply Message Node - reply to the triggering message

Node metadata is loaded from: ../../templates/metadata/nodes/reply_message.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

@workflow_node('reply_message')
class ReplyMessageNode(WorkflowNode):
    """Reply message node - reply to the triggering message"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Priority: content/response (from upstream nodes) > message (original input) > context
        message = inputs.get('content')
        if message in (None, ''):
            message = inputs.get('response')
        if message in (None, ''):
            message = inputs.get('input')
        if message in (None, ''):
            message = inputs.get('message')
        if message in (None, '') and context.message_context:
            message = context.message_context.message_content
        if message is None:
            message = ''

        template = self.get_config('message_template')

        if template:
            message = template
            for key, value in inputs.items():
                try:
                    message = message.replace(f'{{{{{key}}}}}', str(value) if value is not None else '')
                except Exception:
                    pass
            for key, value in context.variables.items():
                try:
                    message = message.replace(f'{{{{variables.{key}}}}}', str(value) if value is not None else '')
                except Exception:
                    pass

        message_str = str(message) if message is not None else ''

        logger.info(
            'ReplyMessageNode resolved message',
            extra={
                'node_id': self.node_id,
                'execution_id': context.execution_id,
                'input_keys': list(inputs.keys()),
                'message_preview': message_str[:200],
                'has_template': bool(template),
                'session_id': context.session_id,
            },
        )

        if not message_str.strip():
            logger.warning(
                'ReplyMessageNode has empty message after resolution',
                extra={
                    'node_id': self.node_id,
                    'execution_id': context.execution_id,
                    'input_keys': list(inputs.keys()),
                },
            )

        # 实际发送消息
        send_success = False
        send_error = None
        if self.ap:
            try:
                from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

                message_chain = MessageChain([Plain(text=message_str)])
                target_type = getattr(context, 'target_type', 'person') or 'person'
                session_id = context.session_id or 'unknown'
                target_id = f'websocket_{session_id}'

                await self.ap.platform_mgr.websocket_proxy_bot.adapter.send_message(
                    target_type=target_type,
                    target_id=target_id,
                    message=message_chain,
                )
                send_success = True
            except Exception as e:
                send_error = str(e)
                logger.error('ReplyMessageNode send message failed: %s', e, exc_info=True)
        else:
            send_error = 'Missing application instance'
            logger.warning(
                'ReplyMessageNode missing application instance',
                extra={
                    'node_id': self.node_id,
                    'execution_id': context.execution_id,
                },
            )

        return {
            'status': 'sent' if send_success else 'failed',
            'message_preview': message_str[:200],
            'error': send_error,
        }
