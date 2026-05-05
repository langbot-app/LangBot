"""Reply Message Node - reply to the triggering message

Node metadata is loaded from: ../../templates/metadata/nodes/reply_message.yaml
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig

logger = logging.getLogger(__name__)


@workflow_node('reply_message')
class ReplyMessageNode(WorkflowNode):
    """Reply message node - reply to the triggering message"""

    type_name = "reply_message"
    category = "action"
    icon = "↩️"
    name = "reply_message"
    description = "reply_message"
    name_zh = "回复消息"
    name_en = "Reply Message"
    description_zh = "回复触发工作流的消息"
    description_en = "Reply to the message that triggered the workflow"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        message = inputs.get("message")
        if message in (None, ""):
            message = inputs.get("input")
        if message in (None, ""):
            message = inputs.get("response")
        if message in (None, "") and context.message_context:
            message = context.message_context.message_content
        if message is None:
            message = ""

        template = self.get_config("message_template")

        if template:
            message = template
            for key, value in inputs.items():
                message = message.replace(f"{{{{{key}}}}}", str(value))
            for key, value in context.variables.items():
                message = message.replace(f"{{{{variables.{key}}}}}", str(value))

        logger.info(
            "ReplyMessageNode resolved message",
            extra={
                'node_id': self.node_id,
                'execution_id': context.execution_id,
                'input_keys': list(inputs.keys()),
                'message_preview': str(message)[:200],
                'has_template': bool(template),
                'session_id': context.session_id,
            },
        )

        if not str(message).strip():
            logger.warning(
                "ReplyMessageNode has empty message after resolution",
                extra={
                    'node_id': self.node_id,
                    'execution_id': context.execution_id,
                    'input_keys': list(inputs.keys()),
                },
            )

        # 实际发送消息
        if self.ap:
            from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
            message_chain = MessageChain([Plain(text=str(message))])
            await self.ap.platform_mgr.websocket_proxy_bot.adapter.send_message(
                target_type='person',
                target_id=f'websocket_{context.session_id}',
                message=message_chain,
            )
        else:
            logger.warning(
                "ReplyMessageNode missing application instance",
                extra={
                    'node_id': self.node_id,
                    'execution_id': context.execution_id,
                },
            )

        return {"status": "sent", "message_id": f"reply_{context.execution_id}"}
