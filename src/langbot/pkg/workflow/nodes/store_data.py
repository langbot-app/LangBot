"""Store Data Node - save data to storage

Node metadata is loaded from: ../../templates/metadata/nodes/store_data.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('store_data')
class StoreDataNode(WorkflowNode):
    """Store data node - save data to storage"""

    type_name = "store_data"
    category = "action"
    icon = "💾"
    name = "store_data"
    description = "store_data"
    name_zh = "存储数据"
    name_en = "Store Data"
    description_zh = "将数据存储到持久化存储"
    description_en = "Store data to persistent storage"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        key = inputs.get("key", "")
        value = inputs.get("value")
        storage_type = self.get_config("storage_type", "session")
        prefix = self.get_config("key_prefix", "")

        full_key = f"{prefix}{key}" if prefix else key

        if storage_type == "session":
            context.set_conversation_variable(full_key, value)
        else:
            context.set_variable(full_key, value)

        return {"status": "stored"}
