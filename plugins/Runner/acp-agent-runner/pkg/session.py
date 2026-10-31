"""ACP session request helpers."""

from __future__ import annotations

import typing

CLAUDE_BUILTIN_TOOLS = [
    "Bash",
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Agent",
]
CLAUDE_ENV_VARS_TO_UNSET = ("CLAUDE_CODE_COORDINATOR_MODE", "ENABLE_TOOL_SEARCH")


def _key_value_pairs(value: typing.Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, list):
        return {
            str(item["name"]): str(item["value"])
            for item in value
            if isinstance(item, dict) and "name" in item and "value" in item
        }
    return {}


def _claude_mcp_servers(mcp_servers: list[dict[str, typing.Any]]) -> dict[str, dict[str, typing.Any]]:
    servers: dict[str, dict[str, typing.Any]] = {}
    for server in mcp_servers:
        name = str(server.get("name") or "").strip()
        transport = str(server.get("type") or "stdio").strip()
        if not name:
            continue
        if transport in {"http", "sse"}:
            servers[name] = {
                "type": transport,
                "url": str(server.get("url") or ""),
                "headers": _key_value_pairs(server.get("headers")),
                "alwaysLoad": True,
            }
        elif transport == "stdio":
            servers[name] = {
                "type": "stdio",
                "command": str(server.get("command") or ""),
                "args": [str(item) for item in server.get("args") or []],
                "env": _key_value_pairs(server.get("env")),
                "alwaysLoad": True,
            }
    return servers


def build_session_params(
    *,
    provider: str,
    cwd: str,
    mcp_servers: list[dict[str, typing.Any]],
    session_id: str = "",
) -> dict[str, typing.Any]:
    """Build isolated session parameters for the selected ACP provider."""
    params: dict[str, typing.Any] = {
        "cwd": cwd,
        "mcpServers": mcp_servers,
    }
    if session_id:
        params["sessionId"] = session_id
    if provider == "claude-code":
        # Claude's SDK otherwise defers MCP tools behind ToolSearch, which is not
        # consistently enabled by the ACP adapter. Load explicit run-scoped tools
        # before the first prompt and keep project/user MCP discovery disabled.
        # Agent stays available because some Anthropic-compatible models only
        # execute MCP tools from a subagent. Workflow, TaskStop, and ToolSearch
        # remain unavailable to avoid detached or duplicate work.
        params["mcpServers"] = []
        params["_meta"] = {
            "claudeCode": {
                "options": {
                    "strictMcpConfig": True,
                    "mcpServers": _claude_mcp_servers(mcp_servers),
                    "tools": CLAUDE_BUILTIN_TOOLS,
                }
            }
        }
    return params
