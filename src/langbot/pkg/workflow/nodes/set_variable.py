"""Set Variable Node - set workflow or conversation variable

Node metadata is loaded from: ../../templates/metadata/nodes/set_variable.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('set_variable')
class SetVariableNode(WorkflowNode):
    """Set variable node - set workflow or conversation variable"""

    type_name = "set_variable"
    category = "action"
    icon = "📝"
    name = "set_variable"
    description = "set_variable"
    name_zh = "设置变量"
    name_en = "Set Variable"
    description_zh = "设置上下文变量值"
    description_en = "Set a context variable value"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        value = inputs.get("value")
        name = self.get_config("variable_name", "")
        scope = self.get_config("variable_scope", "workflow")
        operation = self.get_config("operation", "set")

        if scope == "conversation":
            current = context.get_conversation_variable(name)
        else:
            current = context.get_variable(name)

        if operation == "set":
            final_value = value
        elif operation == "append":
            if isinstance(current, list):
                final_value = current + [value]
            elif isinstance(current, str):
                final_value = current + str(value)
            else:
                final_value = [current, value] if current else [value]
        elif operation == "increment":
            final_value = (current or 0) + (value if isinstance(value, (int, float)) else 1)
        elif operation == "decrement":
            final_value = (current or 0) - (value if isinstance(value, (int, float)) else 1)
        else:
            final_value = value

        if scope == "conversation":
            context.set_conversation_variable(name, final_value)
        else:
            context.set_variable(name, final_value)

        return {"value": final_value}
