"""Long-lived MCP gateway for run-scoped LangBot assets."""

from __future__ import annotations

import asyncio
import dataclasses
import hmac
import json
import secrets
import threading
import time
import typing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_config import AgentMCPServerConfig
from langbot_plugin.api.agent_tools.mcp_protocol import (
    handle_mcp_payload_sync,
    jsonrpc_error,
    mcp_tool_error,
)
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.proxies.runner import RunnerAPIProxy

LANGBOT_AGENT_GATEWAY_SERVER_NAME = "langbot_agent"
LANGBOT_AGENT_GATEWAY_INFO = {"name": "langbot-agent-gateway", "version": "0.1.0"}
LANGBOT_AGENT_GATEWAY_INSTRUCTIONS = (
    "Use langbot_list_assets to discover run-authorized LangBot assets, including "
    "platform_tools. Inspect a tool with langbot_get_tool_detail, then invoke it "
    "with langbot_call_tool. Event-level platform tools have Host-frozen targets. "
    "Tool calls are scoped by the MCP Authorization header or by the run_token "
    "argument. When sandbox APIs are available, check langbot_get_box_status, "
    "acquire or select a Box, and langbot_bind_box before calling sandbox tools. "
    "Import attachments explicitly with langbot_import_box_attachments. Place "
    "output files in the run outbox returned by binding, export them with "
    "langbot_export_box_files, then explicitly deliver them with langbot_reply_files "
    "when reply permission is available."
)
DEFAULT_RUN_TOKEN_TTL_SECONDS = 3600.0
MAX_HTTP_MCP_BODY_BYTES = 1024 * 1024
_HTTP_BODY_TOO_LARGE = object()


class _GatewayMCPResolver:
    def __init__(self, gateway: "AgentAssetGateway", header_token: str) -> None:
        self._gateway = gateway
        self._header_token = header_token

    def list_tools(self) -> list[dict[str, typing.Any]]:
        return AgentRunExternalTools.all_mcp_tools(include_run_token=True)

    def call_tool(
        self,
        name: str,
        arguments: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        return self._gateway._call_tool(
            name,
            arguments,
            header_token=self._header_token,
        )


@dataclasses.dataclass
class AgentAssetGatewayRegistration:
    """A short-lived run registration inside a long-lived asset gateway."""

    gateway: "AgentAssetGateway"
    token: str
    tools: AgentRunExternalTools
    loop: asyncio.AbstractEventLoop
    expires_at: float

    @property
    def server_name(self) -> str:
        return self.gateway.server_name

    @property
    def endpoint(self) -> str:
        return self.gateway.endpoint

    @property
    def http_mcp_endpoint(self) -> str:
        return self.gateway.http_mcp_endpoint

    def http_mcp_server_config(
        self,
        *,
        public_url: str | None = None,
        transport: str = "http",
        include_token_header: bool = True,
    ) -> dict[str, typing.Any]:
        return self.mcp_server(
            public_url=public_url,
            transport=transport,
            include_token_header=include_token_header,
        ).to_dict(include_type=True)

    def mcp_server(
        self,
        *,
        public_url: str | None = None,
        transport: str = "http",
        include_token_header: bool = True,
    ) -> AgentMCPServerConfig:
        headers = {}
        if include_token_header:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "X-LangBot-Agent-Gateway-Token": self.token,
            }
        return AgentMCPServerConfig.http(
            name=self.server_name,
            transport=transport,
            url=(public_url or self.http_mcp_endpoint).strip(),
            headers=headers,
        )

    def stop(self) -> None:
        self.gateway.unregister_run(self.token)


class AgentAssetGateway:
    """Process-long HTTP MCP gateway with per-run authorization tokens."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        request_timeout: float = 60.0,
        server_name: str = LANGBOT_AGENT_GATEWAY_SERVER_NAME,
    ) -> None:
        self.host = host
        self.port = port
        self.request_timeout = request_timeout
        self.server_name = server_name
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._registrations: dict[str, AgentAssetGatewayRegistration] = {}
        self._lock = threading.RLock()
        self._active_handlers = 0

    @property
    def active_handler_count(self) -> int:
        with self._lock:
            return self._active_handlers

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("LangBot Agent Asset Gateway is not started")
        host, port = self._server.server_address[:2]
        return f"http://{str(host)}:{port}"

    @property
    def http_mcp_endpoint(self) -> str:
        return f"{self.endpoint}/mcp"

    def start(self) -> None:
        if self._server is not None:
            return

        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(gateway.request_timeout)
                with gateway._lock:
                    gateway._active_handlers += 1

            def finish(self) -> None:
                try:
                    super().finish()
                finally:
                    with gateway._lock:
                        gateway._active_handlers -= 1

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

                try:
                    payload = self._read_json_payload()
                except OSError:
                    self.close_connection = True
                    return
                if payload is _HTTP_BODY_TOO_LARGE:
                    return
                if isinstance(payload, Exception):
                    self._write_json(
                        400, {"ok": False, "error": f"invalid JSON: {payload}"}
                    )
                    return

                try:
                    result = gateway.handle_http_mcp_request(
                        payload,
                        header_token=self._header_token(),
                    )
                except Exception as e:
                    self._write_json(500, jsonrpc_error(None, -32000, str(e)))
                    return
                if result is None:
                    self._write_empty(202)
                    return
                self._write_json(200, result)

            def handle_one_request(self) -> None:
                try:
                    super().handle_one_request()
                except (TimeoutError, OSError):
                    self.close_connection = True

            def do_DELETE(self) -> None:
                if self.path not in {"/mcp", "/mcp/http"}:
                    self.send_error(404)
                    return
                self.send_response(405)
                self.send_header("Allow", "GET, POST")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _header_token(self) -> str:
                authorization = self.headers.get("Authorization", "").strip()
                if authorization.lower().startswith("bearer "):
                    return authorization[7:].strip()
                for name in (
                    "X-LangBot-Agent-Gateway-Token",
                    "X-LangBot-Agent-MCP-Token",
                ):
                    token = self.headers.get(name, "").strip()
                    if token:
                        return token
                return ""

            def _read_json_payload(self) -> typing.Any:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    return ValueError("invalid Content-Length")
                if length < 0:
                    return ValueError("invalid Content-Length")
                if length > MAX_HTTP_MCP_BODY_BYTES:
                    self._write_empty(413)
                    self.close_connection = True
                    return _HTTP_BODY_TOO_LARGE
                try:
                    body = self.rfile.read(length).decode("utf-8")
                    return json.loads(body) if body else {}
                except TimeoutError:
                    raise
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
            name="langbot-agent-asset-gateway",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        with self._lock:
            self._registrations.clear()
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)

    def register_run(
        self,
        api: RunnerAPIProxy,
        ctx: RunnerContext,
        *,
        token: str | None = None,
        ttl_seconds: float = DEFAULT_RUN_TOKEN_TTL_SECONDS,
    ) -> AgentAssetGatewayRegistration:
        self.start()
        run_token = token or secrets.token_urlsafe(32)
        registration = AgentAssetGatewayRegistration(
            gateway=self,
            token=run_token,
            tools=AgentRunExternalTools(api, ctx),
            loop=asyncio.get_running_loop(),
            expires_at=time.monotonic() + max(1.0, ttl_seconds),
        )
        with self._lock:
            self._registrations[run_token] = registration
        return registration

    def unregister_run(self, token: str) -> None:
        with self._lock:
            self._registrations.pop(token, None)

    def has_active_registrations(self) -> bool:
        self._cleanup_expired_registrations()
        with self._lock:
            return bool(self._registrations)

    def matches_config(
        self,
        *,
        host: str,
        port: int,
        server_name: str,
    ) -> bool:
        return (
            self.host == host and self.port == port and self.server_name == server_name
        )

    def handle_http_mcp_request(
        self,
        payload: typing.Any,
        *,
        header_token: str = "",
    ) -> dict[str, typing.Any] | list[dict[str, typing.Any]] | None:
        return handle_mcp_payload_sync(
            payload,
            _GatewayMCPResolver(self, header_token),
            server_info=LANGBOT_AGENT_GATEWAY_INFO,
            instructions=LANGBOT_AGENT_GATEWAY_INSTRUCTIONS,
        )

    def _call_tool(
        self,
        name: str,
        arguments: dict[str, typing.Any],
        *,
        header_token: str,
    ) -> dict[str, typing.Any]:
        arguments = dict(arguments)
        argument_token = str(arguments.pop("run_token", "") or "").strip()
        token = argument_token or header_token
        registration = self._registration_for_token(token)
        if registration is None:
            return mcp_tool_error("A valid LangBot run_token is required")

        future = asyncio.run_coroutine_threadsafe(
            registration.tools.call_mcp_tool(name, arguments),
            registration.loop,
        )
        try:
            return future.result(timeout=self.request_timeout)
        except Exception as e:
            return mcp_tool_error(str(e))

    def _registration_for_token(
        self, token: str
    ) -> AgentAssetGatewayRegistration | None:
        if not token:
            return None
        self._cleanup_expired_registrations()
        with self._lock:
            registration = self._registrations.get(token)
            if registration is None:
                return None
            if not hmac.compare_digest(registration.token, token):
                return None
            return registration

    def _cleanup_expired_registrations(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired = [
                item_token
                for item_token, item in self._registrations.items()
                if item.expires_at <= now
            ]
            for item_token in expired:
                self._registrations.pop(item_token, None)


_default_gateway: AgentAssetGateway | None = None
_default_gateway_lock = threading.Lock()


def get_default_agent_asset_gateway(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    request_timeout: float = 60.0,
    server_name: str = LANGBOT_AGENT_GATEWAY_SERVER_NAME,
) -> AgentAssetGateway:
    global _default_gateway
    with _default_gateway_lock:
        if (
            _default_gateway is not None
            and not _default_gateway.matches_config(
                host=host,
                port=port,
                server_name=server_name,
            )
            and not _default_gateway.has_active_registrations()
        ):
            _default_gateway.stop()
            _default_gateway = None

        if _default_gateway is None:
            _default_gateway = AgentAssetGateway(
                host=host,
                port=port,
                request_timeout=request_timeout,
                server_name=server_name,
            )
        else:
            _default_gateway.request_timeout = request_timeout
        _default_gateway.start()
        return _default_gateway
