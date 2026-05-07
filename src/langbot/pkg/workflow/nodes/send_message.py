"""Send Message Node - send message to a target

Node metadata is loaded from: ../../templates/metadata/nodes/send_message.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('send_message')
class SendMessageNode(WorkflowNode):
    """Send message node - send message to a target"""

    type_name = "send_message"
    category = "action"
    icon = "📤"
    name = "send_message"
    description = "send_message"
    name_zh = "发送消息"
    name_en = "Send Message"
    description_zh = "向聊天或用户发送消息"
    description_en = "Send a message to a chat or user"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"status": "sent", "message_id": f"msg_{context.execution_id}"}
