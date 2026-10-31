"""Reply Message Node - reply to the triggering message

Node metadata is loaded from: ../../templates/metadata/nodes/reply_message.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.platform.message import At, MessageChain, Plain

from langbot.pkg.workflow.protocol.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node
from ..runtime import current_runtime

logger = logging.getLogger(__name__)


def render_template(template: str, inputs: dict[str, Any], context: ExecutionContext) -> str:
    """Replace ``{{input}}`` and ``{{variables.name}}`` placeholders."""
    message = template
    for key, value in inputs.items():
        message = message.replace(f'{{{{{key}}}}}', '' if value is None else str(value))
    for key, value in context.variables.items():
        message = message.replace(f'{{{{variables.{key}}}}}', '' if value is None else str(value))
    return message


@workflow_node('reply_message')
class ReplyMessageNode(WorkflowNode):
    """Reply message node - reply to the triggering message"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        template = self.get_config('message_template')
        if template:
            message = render_template(str(template), inputs, context)
        else:
            # Priority: upstream content/response > original message
            message = next(
                (inputs.get(key) for key in ('content', 'response', 'input', 'message') if inputs.get(key)),
                context.message_context.message_content if context.message_context else '',
            )
        message_str = '' if message is None else str(message)
        if not message_str.strip():
            return {'status': 'failed', 'message_content': '', 'error': 'Empty message'}

        reply_mode = self.get_config('reply_mode', 'direct')
        components = [Plain(text=message_str)]
        msg_ctx = context.message_context
        if reply_mode == 'at' and msg_ctx and msg_ctx.is_group and msg_ctx.sender_id:
            components.insert(0, At(target=msg_ctx.sender_id))
        try:
            await current_runtime().reply(MessageChain(components), quote_origin=reply_mode == 'quote')
        except Exception as exc:
            logger.error('ReplyMessageNode %s failed to reply: %s', self.node_id, exc, exc_info=True)
            raise

        return {'status': 'sent', 'message_content': message_str, 'error': None}
