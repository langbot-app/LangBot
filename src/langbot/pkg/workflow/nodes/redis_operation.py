"""Redis Operation Node - perform Redis cache operations

Node metadata is loaded from: ../../templates/metadata/nodes/redis_operation.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('redis_operation')
class RedisOperationNode(WorkflowNode):
    """Redis operation node - perform Redis cache operations"""

    type_name = "redis_operation"
    category = "integration"
    icon = "Server"
    name = "redis_operation"
    description = "redis_operation"
    name_zh = "Redis 操作"
    name_en = "Redis Operation"
    description_zh = "执行 Redis 缓存操作"
    description_en = "Perform Redis cache operations"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        connection_url = self.get_config("connection_url", "redis://localhost:6379")
        operation = self.get_config("operation", "get")
        key_template = self.get_config("key_template", "")
        hash_field = self.get_config("hash_field", "")
        ttl = self.get_config("ttl", 0)

        key = inputs.get("key", key_template)
        value = inputs.get("value")

        return {
            "result": None,
            "success": False,
            "_debug": {
                "connection_url": connection_url,
                "operation": operation,
                "key": key,
                "hash_field": hash_field,
                "ttl": ttl,
                "value": value,
            },
        }
