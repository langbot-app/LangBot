"""Message Trigger Node - triggers workflow on message arrival

This module contains the implementation for the Message Trigger workflow node.
Node metadata (label, description, inputs, outputs, config) is loaded from:
../../templates/metadata/nodes/message_trigger.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('message_trigger')
class MessageTriggerNode(WorkflowNode):
    """Message trigger node - triggers workflow on message arrival"""

    type_name = "message_trigger"
    category = "trigger"
    icon = "💬"
    name = "message_trigger"
    description = "message_trigger"
    name_zh = "消息触发"
    name_en = "Message Trigger"
    description_zh = "当收到消息时触发工作流"
    description_en = "Trigger workflow when a message is received"
    
    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        msg_ctx = context.message_context
        
        if msg_ctx:
            return {
                "message": msg_ctx.message_content,
                "sender_id": msg_ctx.sender_id,
                "sender_name": msg_ctx.sender_name,
                "platform": msg_ctx.platform,
                "conversation_id": msg_ctx.conversation_id,
                "is_group": msg_ctx.is_group,
                "context": msg_ctx.model_dump(),
            }
        
        return {
            "message": context.get_variable("message", ""),
            "sender_id": context.get_variable("sender_id", ""),
            "sender_name": context.get_variable("sender_name", ""),
            "platform": context.get_variable("platform", ""),
            "conversation_id": context.get_variable("conversation_id", ""),
            "is_group": context.get_variable("is_group", False),
            "context": context.trigger_data,
        }
