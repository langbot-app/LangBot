"""Memory Store Node - store and retrieve from workflow memory

Node metadata is loaded from: ../../templates/metadata/nodes/memory_store.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


class MemoryHelper:
    """Helper class wrapping context.memory dict with get/set/delete/list_all/append operations"""
    
    def __init__(self, memory_dict: dict[str, Any]):
        self._data = memory_dict
    
    def get(self, key: str, scope: str = "execution", default: Any = None) -> Any:
        """Get a value from memory by key"""
        scoped_key = f"{scope}:{key}" if scope else key
        return self._data.get(scoped_key, default)
    
    def set(self, key: str, value: Any, scope: str = "execution", ttl: int = 0) -> None:
        """Set a value in memory"""
        scoped_key = f"{scope}:{key}" if scope else key
        self._data[scoped_key] = value
    
    def delete(self, key: str, scope: str = "execution") -> None:
        """Delete a value from memory"""
        scoped_key = f"{scope}:{key}" if scope else key
        self._data.pop(scoped_key, None)
    
    def list_all(self, scope: str = "execution") -> dict[str, Any]:
        """List all values in the given scope"""
        prefix = f"{scope}:"
        return {
            k[len(prefix):]: v
            for k, v in self._data.items()
            if k.startswith(prefix)
        }
    
    def append(self, key: str, value: Any, scope: str = "execution", ttl: int = 0) -> list:
        """Append a value to a list in memory"""
        current = self.get(key, scope=scope, default=[])
        if isinstance(current, list):
            current.append(value)
        else:
            current = [current, value]
        self.set(key, current, scope=scope, ttl=ttl)
        return current


@workflow_node('memory_store')
class MemoryStoreNode(WorkflowNode):
    """Memory store node - store and retrieve from workflow memory"""

    type_name = "memory_store"
    category = "integration"
    icon = "HardDrive"
    name = "memory_store"
    description = "memory_store"
    name_zh = "记忆存储"
    name_en = "Memory Store"
    description_zh = "从工作流记忆中存储和检索数据"
    description_en = "Store and retrieve data from workflow memory"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        operation = self.get_config("operation", "get")
        key = self.get_config("key", "")
        scope = self.get_config("scope", "execution")
        ttl = self.get_config("ttl", 0)

        value = inputs.get("value")

        # Wrap context.memory dict with MemoryHelper for structured operations
        memory = MemoryHelper(context.memory)

        try:
            if operation == "get":
                result = memory.get(key, scope=scope)
                return {"result": result, "success": True}
            elif operation == "set":
                memory.set(key, value, scope=scope, ttl=ttl)
                return {"result": value, "success": True}
            elif operation == "delete":
                memory.delete(key, scope=scope)
                return {"result": None, "success": True}
            elif operation == "append":
                result = memory.append(key, value, scope=scope, ttl=ttl)
                return {"result": result, "success": True}
            elif operation == "list":
                result = memory.list_all(scope=scope)
                return {"result": result, "success": True}
            else:
                return {"result": None, "success": False, "error": f"Unknown operation: {operation}"}
        except Exception as e:
            return {"result": None, "success": False, "error": str(e)}
