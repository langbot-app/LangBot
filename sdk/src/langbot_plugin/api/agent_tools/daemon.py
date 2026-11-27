"""Generic daemon relay for external Runner runtimes."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import typing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import websockets

from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_config import AgentMCPServerConfig
from langbot_plugin.api.agent_tools.mcp_protocol import (
    AgentToolsMCPResolver,
    handle_mcp_payload,
    jsonrpc_error,
)

logger = logging.getLogger(__name__)

DEFAULT_DAEMON_HUB_HOST = "127.0.0.1"
DEFAULT_DAEMON_HUB_PORT = 8766
DEFAULT_DAEMON_CONNECT_TIMEOUT = 30.0
DAEMON_MCP_SERVER_INFO = {"name": "langbot-agent-daemon", "version": "0.1.0"}


class AgentRuntimeDaemonError(Exception):
    """Daemon relay error surfaced as a Runner failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "agent_runtime.daemon_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class DaemonConnection(typing.TypedDict):
    daemon_id: str
    websocket: typing.Any
    metadata: dict[str, typing.Any]
    connected_at: float
    last_seen_at: float
    active_jobs: set[str]


class DaemonRunSession(typing.TypedDict):
    job_id: str
    daemon_id: str
    queue: asyncio.Queue[dict[str, typing.Any] | None]
    tools: AgentRunExternalTools | None
    started_at: float


def _to_bool(value: typing.Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _to_int(value: typing.Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def agent_runtime_daemon_config_from_plugin_config(
    config: dict[str, typing.Any] | None,
    *,
    env_prefix: str = "LANGBOT_AGENT_RUNTIME_DAEMON",
    default_host: str = DEFAULT_DAEMON_HUB_HOST,
    default_port: int = DEFAULT_DAEMON_HUB_PORT,
) -> dict[str, typing.Any]:
    """Resolve daemon hub settings from plugin config and environment."""

    data = dict(config or {})
    return {
        "enabled": _to_bool(
            data.get("daemon-enabled", os.environ.get(f"{env_prefix}_ENABLED")),
            False,
        ),
        "host": str(
            data.get("daemon-host")
            or os.environ.get(f"{env_prefix}_HOST")
            or default_host
        ),
        "port": _to_int(
            data.get("daemon-port") or os.environ.get(f"{env_prefix}_PORT"),
            default_port,
        ),
        "token": str(
            data.get("daemon-token") or os.environ.get(f"{env_prefix}_TOKEN") or ""
        ),
    }


async def handle_agent_runtime_mcp_payload(
    tools: AgentRunExternalTools,
    payload: typing.Any,
) -> dict[str, typing.Any] | list[dict[str, typing.Any]] | None:
    """Handle HTTP MCP JSON-RPC payloads forwarded by a daemon."""
    return await handle_mcp_payload(
        payload,
        AgentToolsMCPResolver(tools),
        server_info=DAEMON_MCP_SERVER_INFO,
    )


class AgentRuntimeDaemonHub:
    """WebSocket hub for user-owned runtime daemons."""

    def __init__(self, *, error_code_prefix: str = "agent_runtime") -> None:
        self.host = DEFAULT_DAEMON_HUB_HOST
        self.port = DEFAULT_DAEMON_HUB_PORT
        self.token = ""
        self.error_code_prefix = error_code_prefix
        self._server: typing.Any | None = None
        self._connections: dict[str, DaemonConnection] = {}
        self._jobs: dict[str, DaemonRunSession] = {}
        self._send_lock: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def endpoint(self) -> str:
        if self._server is None:
            return ""
        sockets = getattr(self._server, "sockets", None) or []
        if sockets:
            bound_host, bound_port = sockets[0].getsockname()[:2]
            return f"ws://{bound_host}:{bound_port}"
        return f"ws://{self.host}:{self.port}"

    async def start(self, *, host: str, port: int, token: str = "") -> None:
        if self._server is not None:
            if self.host == host and self.port == port and self.token == token:
                return
            raise AgentRuntimeDaemonError(
                f"daemon hub already started at {self.endpoint}",
                code=f"{self.error_code_prefix}.daemon_hub_conflict",
            )

        self.host = host
        self.port = port
        self.token = token
        self._server = await websockets.serve(self._handle_connection, host, port)
        logger.info("Agent runtime daemon hub listening at %s", self.endpoint)

    async def ensure_started_from_config(self, config: dict[str, typing.Any]) -> None:
        hub_config = agent_runtime_daemon_config_from_plugin_config(config)
        await self.start(
            host=hub_config["host"],
            port=hub_config["port"],
            token=hub_config["token"],
        )

    async def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()
        async with self._lock:
            for connection in list(self._connections.values()):
                with contextlib.suppress(Exception):
                    await connection["websocket"].close(
                        code=1001, reason="hub stopping"
                    )
            self._connections.clear()
            self._jobs.clear()
            self._send_lock.clear()

    async def list_daemons(self) -> list[dict[str, typing.Any]]:
        async with self._lock:
            return [
                {
                    "daemon_id": connection["daemon_id"],
                    "metadata": dict(connection["metadata"]),
                    "connected_at": connection["connected_at"],
                    "last_seen_at": connection["last_seen_at"],
                    "active_jobs": sorted(connection["active_jobs"]),
                }
                for connection in self._connections.values()
            ]

    async def wait_for_daemon(self, daemon_id: str, timeout: float) -> None:
        deadline = time.monotonic() + max(0.1, timeout)
        while True:
            async with self._lock:
                if daemon_id in self._connections:
                    return
            if time.monotonic() >= deadline:
                raise AgentRuntimeDaemonError(
                    f"daemon {daemon_id} is not connected",
                    code=f"{self.error_code_prefix}.daemon_offline",
                    retryable=True,
                )
            await asyncio.sleep(0.2)

    async def run_job(
        self,
        *,
        daemon_id: str,
        payload: dict[str, typing.Any],
        tools: AgentRunExternalTools | None,
        timeout: float,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        if self._server is None:
            raise AgentRuntimeDaemonError(
                "daemon hub is not started",
                code=f"{self.error_code_prefix}.daemon_hub_not_started",
            )

        connection = await self._get_connection(daemon_id)
        job_id = secrets.token_urlsafe(16)
        queue: asyncio.Queue[dict[str, typing.Any] | None] = asyncio.Queue()
        session: DaemonRunSession = {
            "job_id": job_id,
            "daemon_id": daemon_id,
            "queue": queue,
            "tools": tools,
            "started_at": time.monotonic(),
        }

        async with self._lock:
            self._jobs[job_id] = session
            connection["active_jobs"].add(job_id)

        try:
            await self._send(
                daemon_id,
                {
                    "type": "run.start",
                    "job_id": job_id,
                    "payload": payload,
                },
            )
            deadline = time.monotonic() + max(1.0, timeout)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AgentRuntimeDaemonError(
                        "daemon run timed out",
                        code=f"{self.error_code_prefix}.daemon_timeout",
                        retryable=True,
                    )
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
                if item is None:
                    break
                yield item
        finally:
            async with self._lock:
                self._jobs.pop(job_id, None)
                current = self._connections.get(daemon_id)
                if current is not None:
                    current["active_jobs"].discard(job_id)
            with contextlib.suppress(Exception):
                await self._send(daemon_id, {"type": "run.cleanup", "job_id": job_id})

    async def _get_connection(self, daemon_id: str) -> DaemonConnection:
        async with self._lock:
            connection = self._connections.get(daemon_id)
        if connection is None:
            raise AgentRuntimeDaemonError(
                f"daemon {daemon_id} is not connected",
                code=f"{self.error_code_prefix}.daemon_offline",
                retryable=True,
            )
        return connection

    async def _send(self, daemon_id: str, message: dict[str, typing.Any]) -> None:
        connection = await self._get_connection(daemon_id)
        lock = self._send_lock.setdefault(daemon_id, asyncio.Lock())
        async with lock:
            await connection["websocket"].send(
                json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            )

    async def _handle_connection(self, websocket: typing.Any) -> None:
        daemon_id = ""
        try:
            raw_hello = await asyncio.wait_for(websocket.recv(), timeout=10)
            hello = json.loads(raw_hello)
            if not isinstance(hello, dict) or hello.get("type") != "daemon.hello":
                await websocket.close(code=1008, reason="daemon.hello required")
                return

            daemon_id = str(hello.get("daemon_id") or "").strip()
            if not daemon_id:
                await websocket.close(code=1008, reason="daemon_id required")
                return

            provided_token = str(hello.get("token") or "")
            if self.token and not hmac.compare_digest(provided_token, self.token):
                await websocket.close(code=1008, reason="invalid token")
                return

            raw_metadata = hello.get("metadata")
            metadata: dict[str, typing.Any] = (
                dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
            )
            now = time.monotonic()
            async with self._lock:
                old_connection = self._connections.pop(daemon_id, None)
                if old_connection is not None:
                    with contextlib.suppress(Exception):
                        await old_connection["websocket"].close(
                            code=1012, reason="replaced"
                        )
                self._connections[daemon_id] = {
                    "daemon_id": daemon_id,
                    "websocket": websocket,
                    "metadata": dict(metadata),
                    "connected_at": now,
                    "last_seen_at": now,
                    "active_jobs": set(),
                }
                self._send_lock.setdefault(daemon_id, asyncio.Lock())

            await websocket.send(
                json.dumps(
                    {
                        "type": "daemon.ready",
                        "daemon_id": daemon_id,
                        "server_time": time.time(),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            async for raw_message in websocket:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")
                await self._handle_message(daemon_id, raw_message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            logger.exception(
                "Daemon connection failed: daemon_id=%s", daemon_id or "<unregistered>"
            )
        finally:
            if daemon_id:
                await self._drop_connection(daemon_id, websocket)

    async def _drop_connection(self, daemon_id: str, websocket: typing.Any) -> None:
        async with self._lock:
            connection = self._connections.get(daemon_id)
            if connection is not None and connection["websocket"] is websocket:
                self._connections.pop(daemon_id, None)
                self._send_lock.pop(daemon_id, None)
                for job_id in list(connection["active_jobs"]):
                    session = self._jobs.get(job_id)
                    if session is not None:
                        session["queue"].put_nowait(
                            {
                                "type": "run.failed",
                                "data": {
                                    "error": f"daemon {daemon_id} disconnected",
                                    "code": f"{self.error_code_prefix}.daemon_disconnected",
                                    "retryable": True,
                                },
                            }
                        )
                        session["queue"].put_nowait(None)

    async def _handle_message(self, daemon_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid daemon JSON message from %s", daemon_id)
            return
        if not isinstance(message, dict):
            return

        connection = self._connections.get(daemon_id)
        if connection is not None:
            connection["last_seen_at"] = time.monotonic()

        message_type = str(message.get("type") or "")
        if message_type == "daemon.ping":
            await self._send(daemon_id, {"type": "daemon.pong", "time": time.time()})
            return
        if message_type == "run.event":
            await self._handle_run_event(message)
            return
        if message_type == "run.finished":
            await self._finish_job(str(message.get("job_id") or ""))
            return
        if message_type == "mcp.request":
            await self._handle_mcp_request(daemon_id, message)
            return
        logger.debug(
            "Ignoring unknown daemon message type from %s: %s",
            daemon_id,
            message_type,
        )

    async def _handle_run_event(self, message: dict[str, typing.Any]) -> None:
        job_id = str(message.get("job_id") or "")
        session = self._jobs.get(job_id)
        if session is None:
            return
        event = message.get("event")
        if isinstance(event, dict):
            session["queue"].put_nowait(event)

    async def _finish_job(self, job_id: str) -> None:
        session = self._jobs.get(job_id)
        if session is not None:
            session["queue"].put_nowait(None)

    async def _handle_mcp_request(
        self, daemon_id: str, message: dict[str, typing.Any]
    ) -> None:
        request_id = message.get("request_id")
        job_id = str(message.get("job_id") or "")
        session = self._jobs.get(job_id)
        tools = session.get("tools") if session is not None else None

        if tools is None:
            payload: typing.Any = jsonrpc_error(
                None, -32000, "LangBot assets are unavailable for this run"
            )
        else:
            try:
                payload = await handle_agent_runtime_mcp_payload(
                    tools, message.get("payload")
                )
            except Exception as exc:
                payload = jsonrpc_error(None, -32000, str(exc))

        await self._send(
            daemon_id,
            {
                "type": "mcp.response",
                "request_id": request_id,
                "job_id": job_id,
                "payload": payload,
            },
        )


class LocalMCPProxy:
    """Localhost HTTP MCP proxy that forwards requests over a daemon WebSocket."""

    def __init__(
        self,
        daemon: "AgentRuntimeDaemonClient",
        job_id: str,
        *,
        request_timeout: float = 60.0,
        server_name: str = "langbot_agent",
    ) -> None:
        self.daemon = daemon
        self.job_id = job_id
        self.request_timeout = request_timeout
        self.server_name = server_name
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("MCP proxy is not started")
        host, port = self._server.server_address[:2]
        return f"http://{str(host)}:{port}"

    @property
    def http_mcp_endpoint(self) -> str:
        return f"{self.endpoint}/mcp"

    def start(self) -> None:
        if self._server is not None:
            return

        proxy = self

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
                payload = self._read_json_payload()
                if isinstance(payload, Exception):
                    self._write_json(
                        400, {"jsonrpc": "2.0", "id": None, "error": str(payload)}
                    )
                    return
                try:
                    result = proxy.daemon.request_mcp(
                        proxy.job_id, payload, proxy.request_timeout
                    )
                except Exception as exc:
                    result = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32000, "message": str(exc)},
                    }
                if result is None:
                    self._write_empty(202)
                    return
                self._write_json(200, result)

            def _read_json_payload(self) -> typing.Any:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                try:
                    body = self.rfile.read(length).decode("utf-8")
                    return json.loads(body) if body else {}
                except Exception as exc:
                    return exc

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

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="langbot-agent-mcp-proxy",
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

    def mcp_server(self) -> AgentMCPServerConfig:
        return AgentMCPServerConfig.http(
            name=self.server_name,
            url=self.http_mcp_endpoint,
        )

    def server_config(self) -> dict[str, typing.Any]:
        return self.mcp_server().to_dict(include_type=True)


class AgentRuntimeDaemonClient:
    """Outbound WebSocket daemon client for user-owned runtime processes."""

    def __init__(
        self,
        *,
        url: str,
        daemon_id: str,
        token: str = "",
        reconnect_delay: float = 5.0,
        metadata: dict[str, typing.Any] | None = None,
    ) -> None:
        self.url = url
        self.daemon_id = daemon_id
        self.token = token
        self.reconnect_delay = reconnect_delay
        self.metadata = dict(metadata or {})
        self.websocket: typing.Any | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._send_lock = asyncio.Lock()
        self._pending_mcp: dict[str, asyncio.Future[typing.Any]] = {}
        self._job_tasks: dict[str, asyncio.Task[None]] = {}

    async def run_forever(self) -> None:
        self.loop = asyncio.get_running_loop()
        while True:
            try:
                async with websockets.connect(self.url) as websocket:
                    self.websocket = websocket
                    await self._send(
                        {
                            "type": "daemon.hello",
                            "daemon_id": self.daemon_id,
                            "token": self.token,
                            "metadata": {
                                "pid": os.getpid(),
                                "cwd": os.getcwd(),
                                "platform": os.name,
                                **self.metadata,
                            },
                        }
                    )
                    raw_ready = await websocket.recv()
                    ready = json.loads(raw_ready)
                    if (
                        not isinstance(ready, dict)
                        or ready.get("type") != "daemon.ready"
                    ):
                        raise RuntimeError(
                            f"Unexpected daemon ready response: {ready!r}"
                        )
                    logger.info("Connected to daemon hub as %s", self.daemon_id)
                    async for raw_message in websocket:
                        if isinstance(raw_message, bytes):
                            raw_message = raw_message.decode("utf-8")
                        await self._handle_message(raw_message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Disconnected from daemon hub: %s", exc)
            finally:
                self.websocket = None
                for future in list(self._pending_mcp.values()):
                    if not future.done():
                        future.cancel()
                self._pending_mcp.clear()
            await asyncio.sleep(self.reconnect_delay)

    async def run_job(self, job_id: str, payload: dict[str, typing.Any]) -> None:
        raise NotImplementedError

    async def emit_event(self, job_id: str, event: dict[str, typing.Any]) -> None:
        await self._send({"type": "run.event", "job_id": job_id, "event": event})

    async def finish_job(self, job_id: str) -> None:
        await self._send({"type": "run.finished", "job_id": job_id})

    def create_mcp_proxy(
        self,
        job_id: str,
        *,
        request_timeout: float = 60.0,
        server_name: str = "langbot_agent",
    ) -> LocalMCPProxy:
        return LocalMCPProxy(
            self,
            job_id,
            request_timeout=request_timeout,
            server_name=server_name,
        )

    def request_mcp(
        self, job_id: str, payload: typing.Any, timeout: float
    ) -> typing.Any:
        if self.loop is None:
            raise RuntimeError("daemon event loop is not running")
        request_id = secrets.token_urlsafe(12)
        future = asyncio.run_coroutine_threadsafe(
            self._request_mcp_async(job_id, request_id, payload),
            self.loop,
        )
        return future.result(timeout=timeout)

    async def _send(self, message: dict[str, typing.Any]) -> None:
        if self.websocket is None:
            raise RuntimeError("daemon websocket is not connected")
        async with self._send_lock:
            await self.websocket.send(
                json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            )

    async def _handle_message(self, raw_message: str) -> None:
        message = json.loads(raw_message)
        if not isinstance(message, dict):
            return
        message_type = str(message.get("type") or "")
        if message_type == "daemon.pong":
            return
        if message_type == "run.start":
            job_id = str(message.get("job_id") or "")
            raw_payload = message.get("payload")
            payload: dict[str, typing.Any] = (
                dict(raw_payload) if isinstance(raw_payload, dict) else {}
            )
            if not job_id:
                return
            task = asyncio.create_task(self._run_job_wrapper(job_id, payload))
            self._job_tasks[job_id] = task

            def drop_task(_task: asyncio.Task[None]) -> None:
                self._job_tasks.pop(job_id, None)

            task.add_done_callback(drop_task)
            return
        if message_type == "run.cancel":
            job_id = str(message.get("job_id") or "")
            running_task = self._job_tasks.get(job_id)
            if running_task is not None:
                running_task.cancel()
            return
        if message_type == "run.cleanup":
            return
        if message_type == "mcp.response":
            request_id = str(message.get("request_id") or "")
            future = self._pending_mcp.pop(request_id, None)
            if future is not None and not future.done():
                future.set_result(message.get("payload"))
            return

    async def _run_job_wrapper(
        self, job_id: str, payload: dict[str, typing.Any]
    ) -> None:
        try:
            await self.run_job(job_id, payload)
        except asyncio.CancelledError:
            await self.emit_event(
                job_id,
                {
                    "type": "run.failed",
                    "data": {
                        "error": "daemon run cancelled",
                        "code": "agent_runtime.daemon_cancelled",
                        "retryable": True,
                    },
                },
            )
            raise
        except Exception as exc:
            logger.exception("Daemon job failed: %s", exc)
            await self.emit_event(
                job_id,
                {
                    "type": "run.failed",
                    "data": {
                        "error": str(exc),
                        "code": "agent_runtime.daemon_unexpected",
                    },
                },
            )
        finally:
            await self.finish_job(job_id)

    async def _request_mcp_async(
        self, job_id: str, request_id: str, payload: typing.Any
    ) -> typing.Any:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[typing.Any] = loop.create_future()
        self._pending_mcp[request_id] = future
        await self._send(
            {
                "type": "mcp.request",
                "request_id": request_id,
                "job_id": job_id,
                "payload": payload,
            }
        )
        return await future


_global_hubs: dict[str, AgentRuntimeDaemonHub] = {}


def get_agent_runtime_daemon_hub(
    key: str = "default",
    *,
    error_code_prefix: str = "agent_runtime",
) -> AgentRuntimeDaemonHub:
    hub = _global_hubs.get(key)
    if hub is None:
        hub = AgentRuntimeDaemonHub(error_code_prefix=error_code_prefix)
        _global_hubs[key] = hub
    return hub
