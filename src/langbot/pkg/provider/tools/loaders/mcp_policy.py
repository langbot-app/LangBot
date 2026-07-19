from __future__ import annotations

from typing import Any


MCP_STDIO_DISABLED_CODE = 'mcp_stdio_disabled'
MCP_STDIO_DISABLED_MESSAGE = 'Stdio MCP is disabled by instance policy'


class MCPStdioDisabledError(RuntimeError):
    """Raised when an instance-level policy refuses stdio MCP execution."""

    code = MCP_STDIO_DISABLED_CODE

    def __init__(self) -> None:
        super().__init__(MCP_STDIO_DISABLED_MESSAGE)


def stdio_mcp_enabled(ap: Any) -> bool:
    """Return the independent instance-level stdio MCP feature gate.

    The open-source default remains enabled for backwards compatibility.  A
    deployment can disable it with ``mcp.stdio.enabled: false`` (or
    ``MCP__STDIO__ENABLED=false``).  Invalid values fail closed instead of
    accidentally enabling local process execution.
    """

    instance_config = getattr(ap, 'instance_config', None)
    config = getattr(instance_config, 'data', None)
    if not isinstance(config, dict):
        return False
    mcp_config = config.get('mcp', {})
    if not isinstance(mcp_config, dict):
        return False
    stdio_config = mcp_config.get('stdio', {})
    if not isinstance(stdio_config, dict):
        return False
    enabled = stdio_config.get('enabled', True)
    return enabled if isinstance(enabled, bool) else False


def is_stdio_server(server_config: dict[str, Any] | None) -> bool:
    return isinstance(server_config, dict) and str(server_config.get('mode') or '').strip().lower() == 'stdio'


def require_stdio_mcp_enabled(ap: Any, server_config: dict[str, Any] | None) -> None:
    """Fail closed for a stdio server before choosing Box or host transport."""

    if is_stdio_server(server_config) and not stdio_mcp_enabled(ap):
        raise MCPStdioDisabledError()
