"""Component-owned, bounded async MCP listener; never uses the SDK singleton.

Fixed-port collisions fail rather than borrowing another invocation's listener.
The parent invocation revokes tokens and drains all accepted connections.
"""

import asyncio
import hmac
import json
import math
import secrets
import time
from contextvars import copy_context

from langbot_plugin.api.agent_tools.asset_gateway import (
    LANGBOT_AGENT_GATEWAY_INFO,
    LANGBOT_AGENT_GATEWAY_INSTRUCTIONS,
)
from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_protocol import handle_mcp_payload, mcp_tool_error
from langbot_plugin.api.proxies.invocation import invocation_capability

MAX_BODY = 1024 * 1024
MAX_CONNECTIONS = 16


class Registration:
    def __init__(self, gateway, api, ctx, ttl, authority, context):
        self.context = context
        self.authority = authority
        self.gateway = gateway
        self.token = secrets.token_urlsafe(32)
        self.tools = AgentRunExternalTools(api, ctx)
        self.expires_at = time.monotonic() + ttl

    @property
    def endpoint(self):
        return self.gateway.endpoint

    @property
    def http_mcp_endpoint(self):
        return self.endpoint + "/mcp"

    async def stop(self):
        await self.gateway.unregister(self.token)


class Gateway:
    def __init__(self, timeout):
        self.request_timeout = timeout
        self.registrations = {}
        self.server = None
        self.tasks = set()
        self.call_tasks = {}
        self.pool = None
        self.key = None
        self.endpoint = ""

    def _registration_for_token(self, token):
        r = self.registrations.get(token)
        if (
            r is not None
            and r.authority.active
            and time.monotonic() < r.expires_at
            and hmac.compare_digest(r.token, token)
        ):
            return r
        return None

    def connected(self, reader, writer):
        if len(self.tasks) >= MAX_CONNECTIONS:
            writer.close()
            return
        task = asyncio.create_task(self.serve(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def serve(self, reader, writer):
        try:
            async with asyncio.timeout(self.request_timeout):
                head = await reader.readuntil(b"\r\n\r\n")
                if len(head) > 16384:
                    raise ValueError("headers too large")
                lines = head.decode("latin1").split("\r\n")
                method, path, _ = lines[0].split(" ", 2)
                headers = {}
                for line in lines[1:]:
                    if not line:
                        continue
                    key, value = line.split(":", 1)
                    key = key.lower()
                    if key in headers:
                        raise ValueError("duplicate header")
                    headers[key] = value.strip()
                if "transfer-encoding" in headers:
                    raise ValueError("chunked requests unsupported")
                length = int(headers.get("content-length", "0"))
                if not 0 <= length <= MAX_BODY:
                    await self.respond(writer, 413, {"error": "request too large"})
                    return
                if method == "GET" and path == "/healthz":
                    await self.respond(writer, 200, {"ok": True})
                    return
                if method != "POST" or path not in ("/mcp", "/mcp/http"):
                    await self.respond(writer, 404, {"error": "not found"})
                    return
                payload = json.loads(await reader.readexactly(length))
                if isinstance(payload, list) and len(payload) > 32:
                    raise ValueError("batch too large")
                gateway = self
                header_token = headers.get("authorization", "")
                if header_token.lower().startswith("bearer "):
                    header_token = header_token[7:].strip()
                else:
                    header_token = headers.get(
                        "x-langbot-agent-gateway-token", headers.get("x-langbot-agent-mcp-token", "")
                    )

                class Resolver:
                    async def list_tools(self):
                        return AgentRunExternalTools.all_mcp_tools(include_run_token=True)

                    async def call_tool(self, name, arguments):
                        arguments = dict(arguments)
                        token = str(arguments.pop("run_token", "") or header_token)
                        registration = gateway._registration_for_token(token)
                        if registration is None:
                            return mcp_tool_error("A valid LangBot run_token is required")
                        request_task = asyncio.current_task()
                        gateway.call_tasks[request_task] = token
                        try:
                            registration.authority.require_active()
                            tool_task = registration.context.run(
                                asyncio.create_task,
                                registration.tools.call_mcp_tool(name, arguments),
                            )
                            try:
                                result = await tool_task
                            except asyncio.CancelledError:
                                tool_task.cancel()
                                await asyncio.gather(tool_task, return_exceptions=True)
                                raise
                            registration.authority.require_active()
                            return result
                        finally:
                            gateway.call_tasks.pop(request_task, None)

                result = await handle_mcp_payload(
                    payload,
                    Resolver(),
                    server_info=LANGBOT_AGENT_GATEWAY_INFO,
                    instructions=LANGBOT_AGENT_GATEWAY_INSTRUCTIONS,
                )
                await self.respond(writer, 202 if result is None else 200, result)
        except (ValueError, asyncio.LimitOverrunError, asyncio.IncompleteReadError):
            pass
        except (TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def respond(self, writer, status, result):
        body = b"" if result is None else json.dumps(result, ensure_ascii=False).encode()
        if len(body) > MAX_BODY:
            status, body = 413, b'{"error":"response too large"}'
        writer.write(
            f"HTTP/1.1 {status} Response\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()

    async def unregister(self, token):
        self.registrations.pop(token, None)
        pending = [task for task, owner in self.call_tasks.items() if owner == token]
        for task in pending:
            task.cancel()
        if not self.registrations:
            # Remove from the pool before any await: no new lease on a closing listener.
            if self.pool is not None and self.pool.get(self.key) is self:
                del self.pool[self.key]
            await self.stop()
        elif pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def stop(self):
        self.registrations.clear()  # revoke before any await
        if self.server is not None:
            self.server.close()
        for task in tuple(self.tasks):
            task.cancel()

        async def drain():
            if self.server is not None:
                await self.server.wait_closed()
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)

        cleanup = asyncio.create_task(drain())
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError


async def register_assets(owner, api, ctx, config):
    timeout = float(config["asset_gateway_request_timeout"])
    ttl = float(config["asset_gateway_token_ttl"])
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("asset gateway request timeout must be in (0, 120]")
    if not math.isfinite(ttl) or not 0 < ttl <= 3600:
        raise ValueError("asset gateway token TTL must be in (0, 3600]")
    # This owner is the SDK-created component, NOT a config-supplied tenant name.
    # One component per artifact; registrations carry revocable invocation authority.
    authority = invocation_capability(owner._plugin_runtime_handler)
    if authority is None:
        raise RuntimeError("Asset gateway requires an active run-scoped authority")
    if not hasattr(owner, "_asset_gateway_pool"):
        owner._asset_gateway_pool = {}
        owner._asset_gateway_lock = asyncio.Lock()
    pool = owner._asset_gateway_pool
    key = (config["asset_gateway_host"], config["asset_gateway_port"], timeout)
    async with owner._asset_gateway_lock:
        gateway = pool.get(key)
        if gateway is None:
            gateway = Gateway(timeout)
            gateway.pool, gateway.key = pool, key
            try:
                gateway.server = await asyncio.start_server(gateway.connected, key[0], key[1], limit=16384, backlog=16)
                host, port = gateway.server.sockets[0].getsockname()[:2]
                host = f"[{host}]" if ":" in host else host
                gateway.endpoint = f"http://{host}:{port}"
                pool[key] = gateway
            except BaseException:
                await gateway.stop()
                raise
        authority.require_active()
        registration = Registration(gateway, api, ctx, ttl, authority, copy_context())
        gateway.registrations[registration.token] = registration
        return registration
