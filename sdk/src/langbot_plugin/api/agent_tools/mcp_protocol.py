"""Shared MCP JSON-RPC handling for LangBot Agent tool surfaces."""

from __future__ import annotations

import typing

DEFAULT_MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPMethodNotFoundError(Exception):
    """Raised when a JSON-RPC MCP method is not supported."""


class MCPToolResolver(typing.Protocol):
    """Async resolver for an MCP tool surface."""

    async def list_tools(self) -> list[dict[str, typing.Any]]: ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, typing.Any],
    ) -> dict[str, typing.Any]: ...


class SyncMCPToolResolver(typing.Protocol):
    """Sync resolver for an MCP tool surface."""

    def list_tools(self) -> list[dict[str, typing.Any]]: ...

    def call_tool(
        self,
        name: str,
        arguments: dict[str, typing.Any],
    ) -> dict[str, typing.Any]: ...


class AgentToolsMCPResolver:
    """Adapter for AgentRunExternalTools-like objects."""

    def __init__(self, tools: typing.Any, *, include_run_token: bool = False) -> None:
        self._tools = tools
        self._include_run_token = include_run_token

    async def list_tools(self) -> list[dict[str, typing.Any]]:
        return self._tools.mcp_tools(include_run_token=self._include_run_token)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        return await self._tools.call_mcp_tool(name, arguments)


def jsonrpc_result(
    message_id: typing.Any,
    result: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def jsonrpc_error(
    message_id: typing.Any,
    code: int,
    message: str,
) -> dict[str, typing.Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def mcp_tool_error(message: str) -> dict[str, typing.Any]:
    return {
        "isError": True,
        "content": [
            {
                "type": "text",
                "text": message,
            }
        ],
    }


def initialize_result(
    params: dict[str, typing.Any],
    *,
    server_info: dict[str, typing.Any],
    instructions: str | None = None,
) -> dict[str, typing.Any]:
    result: dict[str, typing.Any] = {
        "protocolVersion": str(
            params.get("protocolVersion") or DEFAULT_MCP_PROTOCOL_VERSION
        ),
        "capabilities": {
            "tools": {
                "listChanged": False,
            }
        },
        "serverInfo": server_info,
    }
    if instructions:
        result["instructions"] = instructions
    return result


async def handle_mcp_payload(
    payload: typing.Any,
    resolver: MCPToolResolver,
    *,
    server_info: dict[str, typing.Any],
    instructions: str | None = None,
) -> dict[str, typing.Any] | list[dict[str, typing.Any]] | None:
    if isinstance(payload, list):
        if not payload:
            return jsonrpc_error(None, -32600, "Invalid request")
        responses: list[dict[str, typing.Any]] = []
        for item in payload:
            response = await handle_mcp_message(
                item,
                resolver,
                server_info=server_info,
                instructions=instructions,
            )
            if response is not None:
                responses.append(response)
        return responses or None
    return await handle_mcp_message(
        payload,
        resolver,
        server_info=server_info,
        instructions=instructions,
    )


async def handle_mcp_message(
    message: typing.Any,
    resolver: MCPToolResolver,
    *,
    server_info: dict[str, typing.Any],
    instructions: str | None = None,
) -> dict[str, typing.Any] | None:
    if not isinstance(message, dict):
        return jsonrpc_error(None, -32600, "Invalid request")

    message_id = message.get("id")
    method = str(message.get("method") or "")
    params = _params_dict(message.get("params"))

    if message_id is None:
        return None

    if method == "initialize":
        return jsonrpc_result(
            message_id,
            initialize_result(
                params,
                server_info=server_info,
                instructions=instructions,
            ),
        )
    if method == "ping":
        return jsonrpc_result(message_id, {})

    try:
        result = await handle_mcp_tool_method(method, params, resolver)
    except MCPMethodNotFoundError:
        return jsonrpc_error(message_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return jsonrpc_error(message_id, -32000, str(exc))
    return jsonrpc_result(message_id, result)


async def handle_mcp_tool_method(
    method: str,
    params: dict[str, typing.Any],
    resolver: MCPToolResolver,
) -> dict[str, typing.Any]:
    if method == "tools/list":
        return {"tools": await resolver.list_tools()}
    if method == "tools/call":
        name, arguments = _tool_call_args(params)
        return await resolver.call_tool(name, arguments)
    raise MCPMethodNotFoundError(method)


def handle_mcp_payload_sync(
    payload: typing.Any,
    resolver: SyncMCPToolResolver,
    *,
    server_info: dict[str, typing.Any],
    instructions: str | None = None,
) -> dict[str, typing.Any] | list[dict[str, typing.Any]] | None:
    if isinstance(payload, list):
        if not payload:
            return jsonrpc_error(None, -32600, "Invalid request")
        responses: list[dict[str, typing.Any]] = []
        for item in payload:
            response = handle_mcp_message_sync(
                item,
                resolver,
                server_info=server_info,
                instructions=instructions,
            )
            if response is not None:
                responses.append(response)
        return responses or None
    return handle_mcp_message_sync(
        payload,
        resolver,
        server_info=server_info,
        instructions=instructions,
    )


def handle_mcp_message_sync(
    message: typing.Any,
    resolver: SyncMCPToolResolver,
    *,
    server_info: dict[str, typing.Any],
    instructions: str | None = None,
) -> dict[str, typing.Any] | None:
    if not isinstance(message, dict):
        return jsonrpc_error(None, -32600, "Invalid request")

    message_id = message.get("id")
    method = str(message.get("method") or "")
    params = _params_dict(message.get("params"))

    if message_id is None:
        return None

    if method == "initialize":
        return jsonrpc_result(
            message_id,
            initialize_result(
                params,
                server_info=server_info,
                instructions=instructions,
            ),
        )
    if method == "ping":
        return jsonrpc_result(message_id, {})

    try:
        result = handle_mcp_tool_method_sync(method, params, resolver)
    except MCPMethodNotFoundError:
        return jsonrpc_error(message_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return jsonrpc_error(message_id, -32000, str(exc))
    return jsonrpc_result(message_id, result)


def handle_mcp_tool_method_sync(
    method: str,
    params: dict[str, typing.Any],
    resolver: SyncMCPToolResolver,
) -> dict[str, typing.Any]:
    if method == "tools/list":
        return {"tools": resolver.list_tools()}
    if method == "tools/call":
        name, arguments = _tool_call_args(params)
        return resolver.call_tool(name, arguments)
    raise MCPMethodNotFoundError(method)


def _params_dict(raw_params: typing.Any) -> dict[str, typing.Any]:
    return raw_params if isinstance(raw_params, dict) else {}


def _tool_call_args(params: dict[str, typing.Any]) -> tuple[str, dict[str, typing.Any]]:
    name = str(params.get("name") or "")
    raw_arguments = params.get("arguments") or {}
    arguments = dict(raw_arguments) if isinstance(raw_arguments, dict) else {}
    return name, arguments
