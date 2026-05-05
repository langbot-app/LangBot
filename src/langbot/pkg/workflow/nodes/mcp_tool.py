"""MCP Tool Node - Invoke MCP (Model Context Protocol) tools

This module contains the implementation for the MCP Tool workflow node.
Node metadata (label, description, inputs, outputs, config) is loaded from:
../../templates/metadata/nodes/mcp_tool.yaml

The i18n for label and description is handled on the frontend side.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('mcp_tool')
class MCPToolNode(WorkflowNode):
    """MCP tool node - invoke MCP (Model Context Protocol) tools"""

    # Node type for registration
    type_name = "mcp_tool"
    
    # Category and icon - these are not i18n
    category = "integration"
    icon = "Wrench"
    
    # Name and description - i18n handled on frontend side
    # Frontend will use node type key to look up translation
    name = "mcp_tool"
    description = "mcp_tool"
    name_zh = "MCP 工具"
    name_en = "MCP Tool"
    description_zh = "调用 MCP 工具"
    description_en = "Invoke an MCP (Model Context Protocol) tool"
    
    # Inputs/outputs/config - loaded from YAML at runtime
    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        """Execute the MCP tool node
        
        Args:
            inputs: Input data from connected nodes
            context: Execution context with workflow state
            
        Returns:
            Dictionary of output values
        """
        server_name = self.get_config("server_name", "")
        tool_name = self.get_config("tool_name", "")
        arguments_template = self.get_config("arguments_template", "")
        timeout = self.get_config("timeout", 30)

        arguments = inputs.get("arguments", arguments_template)

        return {
            "result": None,
            "success": False,
            "error": f"MCP tool '{server_name}/{tool_name}' not implemented yet",
            "_debug": {
                "server_name": server_name,
                "tool_name": tool_name,
                "arguments": arguments,
                "timeout": timeout,
            },
        }
