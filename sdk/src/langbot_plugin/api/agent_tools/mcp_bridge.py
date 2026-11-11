"""MCP adapter for annotated LangBot Runner tools."""

from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import sys
import threading
import typing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_config import AgentMCPServerConfig
from langbot_plugin.api.agent_tools.mcp_protocol import (
    AgentToolsMCPResolver,
    MCPMethodNotFoundError,
    handle_mcp_payload,
    handle_mcp_tool_method,
    jsonrpc_error,
)
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.proxies.runner import RunnerAPIProxy

LANGBOT_AGENT_MCP_SERVER_NAME = "langbot_agent"
MCP_SERVER_INFO = {"name": "langbot-agent", "version": "0.1.0"}


def merge_mcp_server_config(
    base_config: dict[str, typing.Any] | None,
    server_config: dict[str, typing.Any],
    *,
    server_name: str = LANGBOT_AGENT_MCP_SERVER_NAME,
) -> dict[str, typing.Any]:
    """Return an MCP config with a LangBot run-scoped server added."""

    data = dict(base_config or {})
    servers = data.get("mcpServers") or data.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        raise ValueError("MCP config mcpServers must be an object")

    merged_servers = dict(servers)
    merged_servers[server_name] = server_config
    data["mcpServers"] = merged_servers
    data.pop("mcp_servers", None)
    return data


class AgentRunMCPBridge:
    """Run-scoped localhost bridge used by stdio MCP proxy processes."""

    def __init__(
        self,
        tools: AgentRunExternalTools,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        request_timeout: float = 60.0,
        server_name: str = LANGBOT_AGENT_MCP_SERVER_NAME,
    ) -> None:
        self.tools = tools
        self._mcp_resolver = AgentToolsMCPResolver(tools)
        self.host = host
        self.port = port
        self.request_timeout = request_timeout
        self.server_name = server_name
        self.token = secrets.token_urlsafe(32)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def from_run_api(
        cls,
        api: RunnerAPIProxy,
        ctx: RunnerContext,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        request_timeout: float = 60.0,
        server_name: str = LANGBOT_AGENT_MCP_SERVER_NAME,
    ) -> "AgentRunMCPBridge":
        return cls(
            AgentRunExternalTools(api, ctx),
            host=host,
            port=port,
            request_timeout=request_timeout,
            server_name=server_name,
        )

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("LangBot Agent MCP bridge is not started")
        host, port = self._server.server_address[:2]
        return f"http://{str(host)}:{port}"

    @property
    def http_mcp_endpoint(self) -> str:
        return f"{self.endpoint}/mcp/http"

    def start(self) -> None:
        if self._server is not None:
            return

        self._loop = asyncio.get_running_loop()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: typing.Any) -> None:
                return

            def do_GET(self) -> None:
                if self.path != "/healthz":
                    self.send_error(404)
                    return
                self._write_json(200, {"ok": True})

            def do_POST(self) -> None:
                if self.path not in {"/mcp", "/mcp/http"}:
                    self.send_error(404)
                    return
                if not self._authorized():
                    self._write_json(401, {"ok": False, "error": "unauthorized"})
                    return

                payload = self._read_json_payload()
                if isinstance(payload, Exception):
                    self._write_json(
                        400, {"ok": False, "error": f"invalid JSON: {payload}"}
                    )
                    return

                if self.path == "/mcp/http":
                    assert bridge._loop is not None
                    future = asyncio.run_coroutine_threadsafe(
                        bridge.handle_http_mcp_request(payload),
                        bridge._loop,
                    )
                    try:
                        result = future.result(timeout=bridge.request_timeout)
                    except Exception as e:
                        self._write_json(500, jsonrpc_error(None, -32000, str(e)))
                        return
                    if result is None:
                        self._write_empty(202)
                        return
                    self._write_json(200, result)
                    return

                if not isinstance(payload, dict):
                    self._write_json(
                        400, {"ok": False, "error": "request must be an object"}
                    )
                    return

                try:
                    assert bridge._loop is not None
                    future = asyncio.run_coroutine_threadsafe(
                        bridge.handle_mcp_method(
                            str(payload.get("method") or ""),
                            payload.get("params") or {},
                        ),
                        bridge._loop,
                    )
                    result = future.result(timeout=bridge.request_timeout)
                except Exception as e:
                    self._write_json(500, {"ok": False, "error": str(e)})
                    return
                self._write_json(200, {"ok": True, "result": result})

            def _authorized(self) -> bool:
                token = self.headers.get("X-LangBot-Agent-MCP-Token", "")
                authorization = self.headers.get("Authorization", "")
                return hmac.compare_digest(token, bridge.token) or hmac.compare_digest(
                    authorization,
                    f"Bearer {bridge.token}",
                )

            def _read_json_payload(self) -> typing.Any:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                try:
                    body = self.rfile.read(length).decode("utf-8")
                    return json.loads(body) if body else {}
                except Exception as e:
                    return e

            def _write_json(self, status: int, payload: typing.Any) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _write_empty(self, status: int) -> None:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="langbot-agent-mcp-bridge",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)

    def mcp_server(
        self, *, transport: str = "stdio", public_url: str | None = None
    ) -> AgentMCPServerConfig:
        """Return neutral MCP server config for external runtimes."""

        if transport == "http":
            return AgentMCPServerConfig.http(
                name=self.server_name,
                url=(public_url or self.http_mcp_endpoint).strip(),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "X-LangBot-Agent-MCP-Token": self.token,
                },
            )
        if transport != "stdio":
            raise ValueError("MCP bridge transport must be stdio or http")
        return AgentMCPServerConfig.stdio(
            name=self.server_name,
            command=sys.executable,
            args=["-m", "langbot_plugin.api.agent_tools.mcp_stdio"],
            env={
                "LANGBOT_AGENT_MCP_ENDPOINT": self.endpoint,
                "LANGBOT_AGENT_MCP_TOKEN": self.token,
            },
        )

    def mcp_server_config(self) -> dict[str, typing.Any]:
        """Return stdio MCP config for external harnesses."""

        return self.mcp_server().to_dict()

    def http_mcp_server_config(
        self,
        *,
        public_url: str | None = None,
        transport: str = "http",
    ) -> dict[str, typing.Any]:
        """Return HTTP MCP server config for external harnesses."""

        return self.mcp_server(transport=transport, public_url=public_url).to_dict(
            include_type=True
        )

    def merged_mcp_config(
        self, base_config: dict[str, typing.Any] | None = None
    ) -> dict[str, typing.Any]:
        return merge_mcp_server_config(
            base_config,
            self.mcp_server_config(),
            server_name=self.server_name,
        )

    async def handle_mcp_method(
        self, method: str, params: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        try:
            return await handle_mcp_tool_method(method, params, self._mcp_resolver)
        except MCPMethodNotFoundError as exc:
            raise ValueError(f"Unsupported MCP bridge method: {method}") from exc

    async def handle_http_mcp_request(
        self, payload: typing.Any
    ) -> dict[str, typing.Any] | list[dict[str, typing.Any]] | None:
        return await handle_mcp_payload(
            payload,
            self._mcp_resolver,
            server_info=MCP_SERVER_INFO,
        )
