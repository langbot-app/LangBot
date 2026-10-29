"""Plugin-owned coding-relay-v1; derived from SDK b5, see RELAY-NOTICE.md."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import typing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
        "host": str(data.get("daemon-host") or os.environ.get(f"{env_prefix}_HOST") or default_host),
        "port": _to_int(
            data.get("daemon-port") or os.environ.get(f"{env_prefix}_PORT"),
            default_port,
        ),
        "token": str(data.get("daemon-token") or os.environ.get(f"{env_prefix}_TOKEN") or ""),
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
    """One installation listener; jobs belong to socket incarnations, not names.

    An unresolved remote job fences its display ID. Shared workers persist
    pending markers across restarts; only an operator who has verified remote
    quiescence may remove an unresolved marker.
    The daemon is a trusted execution target, not a hostile-process sandbox.
    """

    def __init__(self, *, error_code_prefix: str = "agent_runtime", state_dir=None) -> None:
        self.host = DEFAULT_DAEMON_HUB_HOST
        self.port = DEFAULT_DAEMON_HUB_PORT
        self.token = ""
        self.error_code_prefix = error_code_prefix
        self.cancel_timeout = 10.0
        self._server = None
        self._connections = {}
        self._jobs = {}
        self._fenced = set()
        self._state_dir = (
            Path(state_dir)
            if state_dir is not None
            else (
                Path("/data/.coding-relay-v1") / error_code_prefix
                if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared"
                else None
            )
        )
        if self._state_dir is not None and self._state_dir.exists():
            self._fenced.update(p.read_text() for p in self._state_dir.glob("*.pending"))
        self._start_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def endpoint(self) -> str:
        if self._server is None:
            return ""
        host, port = self._server.sockets[0].getsockname()[:2]
        return f"ws://{host}:{port}"

    def _error(self, message, code):
        return AgentRuntimeDaemonError(message, code=f"{self.error_code_prefix}.{code}")

    async def start(self, *, host: str, port: int, token: str = "") -> None:
        async with self._start_lock:
            if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
                if len(token) < 32 or len(set(token)) < 12 or token.strip() != token:
                    raise self._error(
                        "shared daemon-token must be installation-specific: generate with "
                        "python -c 'import secrets; print(secrets.token_urlsafe(32))'",
                        "daemon_token_required",
                    )
            if self._server is not None:
                if (self.host, self.port, self.token) == (host, port, token):
                    return
                raise self._error(
                    "daemon hub already started with different config; restart after draining runs",
                    "daemon_hub_conflict",
                )
            try:
                server = await websockets.serve(self._handle_connection, host, port)
            except OSError as exc:
                raise self._error(
                    f"cannot bind daemon listener {host}:{port}; configure a unique daemon-port "
                    "per installation and route clients to it",
                    "daemon_bind_failed",
                ) from exc
            self.host, self.port, self.token, self._server = host, port, token, server

    async def ensure_started_from_config(self, config):
        conf = agent_runtime_daemon_config_from_plugin_config(config)
        await self.start(host=conf["host"], port=conf["port"], token=conf["token"])

    async def stop(self) -> None:
        async with self._start_lock:
            # Cancel while the reader is still available to receive acknowledgements.
            await asyncio.gather(*(self._settle(s) for s in list(self._jobs.values())))
            server, self._server = self._server, None
            if server is not None:
                server.close()
                await server.wait_closed()

    async def list_daemons(self):
        return [
            dict(
                daemon_id=c["daemon_id"],
                metadata=c["metadata"],
                connected_at=c["connected_at"],
                last_seen_at=c["last_seen_at"],
                active_jobs=sorted(c["active_jobs"]),
            )
            for c in self._connections.values()
        ]

    async def wait_for_daemon(self, daemon_id, timeout):
        deadline = time.monotonic() + max(0.1, timeout)
        while True:
            self._check_fence(daemon_id)
            if daemon_id in self._connections:
                return
            if time.monotonic() >= deadline:
                raise self._error(f"daemon {daemon_id} is not connected", "daemon_offline")
            await asyncio.sleep(0.05)

    def _check_fence(self, daemon_id):
        if any(s["daemon_id"] == daemon_id and s["cancelling"] for s in self._jobs.values()):
            raise self._error(f"daemon {daemon_id} is cancelling; await cleanup before reuse", "daemon_cancelling")
        if daemon_id in self._fenced:
            raise self._error(
                f"daemon {daemon_id} fenced: cleanup unconfirmed; stop remote jobs before restarting this worker",
                "daemon_fenced",
            )

    async def run_job(self, *, daemon_id, payload, tools, timeout):
        if not self.is_running:
            raise self._error("daemon hub is not started", "daemon_hub_not_started")
        self._check_fence(daemon_id)
        owner = self._connections.get(daemon_id)
        if owner is None:
            raise self._error(f"daemon {daemon_id} is not connected", "daemon_offline")
        if len(self._jobs) >= 128:
            raise self._error("daemon job capacity reached", "daemon_busy")
        job_id = secrets.token_urlsafe(16)
        session = dict(
            job_id=job_id,
            daemon_id=daemon_id,
            owner=owner,
            queue=asyncio.Queue(),
            tools=tools,
            done=asyncio.Event(),
            cancelling=False,
        )
        # Write before dispatch: a worker crash cannot silently erase an active
        # remote lease. Only acknowledged quiescence removes the marker.
        marker = self._marker(daemon_id)
        if marker is not None and not owner["active_jobs"]:
            marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with marker.open("x") as handle:
                handle.write(daemon_id)
                handle.flush()
                os.fsync(handle.fileno())
        self._jobs[job_id] = session
        owner["active_jobs"].add(job_id)
        try:
            await self._send(owner, dict(type="run.start", job_id=job_id, payload=payload))
            async with asyncio.timeout(max(0.01, timeout)):
                while True:
                    item = await session["queue"].get()
                    if item is None:
                        break
                    yield item
        finally:
            # Repeated caller cancellation must not interrupt cleanup/fencing.
            cleanup = asyncio.create_task(self._settle(session))
            interrupted = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    interrupted = True
            cleanup.result()
            if interrupted:
                raise asyncio.CancelledError

    def _marker(self, daemon_id):
        if self._state_dir is None:
            return None
        return self._state_dir / (hashlib.sha256(daemon_id.encode()).hexdigest() + ".pending")

    async def _settle(self, session):
        session["cancelling"] = True
        session["tools"] = None
        owner = session["owner"]
        try:
            if not session["done"].is_set():
                async with asyncio.timeout(self.cancel_timeout):
                    await self._send(owner, dict(type="run.cancel", job_id=session["job_id"]))
                    await session["done"].wait()
        except (Exception, asyncio.CancelledError):
            self._fenced.add(session["daemon_id"])
        finally:
            self._jobs.pop(session["job_id"], None)
            owner["active_jobs"].discard(session["job_id"])
            if not owner["active_jobs"] and session["daemon_id"] not in self._fenced:
                marker = self._marker(session["daemon_id"])
                if marker is not None:
                    marker.unlink(missing_ok=True)

    async def _send(self, connection, message):
        async with connection["send_lock"]:
            await connection["websocket"].send(json.dumps(message, ensure_ascii=False))

    async def _handle_connection(self, websocket):
        connection = None
        try:
            hello = json.loads(await asyncio.wait_for(websocket.recv(), 10))
            if not isinstance(hello, dict) or hello.get("type") != "daemon.hello":
                await websocket.close(code=1008, reason="daemon.hello required")
                return
            name = str(hello.get("daemon_id") or "").strip()
            if not name or len(name) > 128:
                await websocket.close(code=1008, reason="daemon_id required (max 128 characters)")
                return
            if self.token and not hmac.compare_digest(str(hello.get("token") or ""), self.token):
                await websocket.close(code=1008, reason="invalid token")
                return
            if hello.get("protocol") != "coding-relay-v1":
                await websocket.close(
                    code=1008, reason="upgrade daemon.py and pkg from matching plugin: coding-relay-v1 required"
                )
                return
            # Never silently replace a live socket, even when its display ID matches.
            marker = self._marker(name)
            if (
                name in self._connections
                or name in self._fenced
                or (marker is not None and marker.exists())
                or len(self._connections) + len(self._fenced) >= 128
            ):
                await websocket.close(code=1008, reason="daemon ID connected or fenced; verify cleanup before reuse")
                return
            now = time.monotonic()
            connection = dict(
                daemon_id=name,
                websocket=websocket,
                metadata=hello.get("metadata") or {},
                connected_at=now,
                last_seen_at=now,
                active_jobs=set(),
                send_lock=asyncio.Lock(),
            )
            self._connections[name] = connection
            await self._send(connection, dict(type="daemon.ready", daemon_id=name, protocol="coding-relay-v1"))
            async for raw in websocket:
                await self._handle_message(connection, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            logger.exception("Daemon connection failed")
        finally:
            if connection is not None:
                if self._connections.get(connection["daemon_id"]) is connection:
                    self._connections.pop(connection["daemon_id"], None)
                for job_id in list(connection["active_jobs"]):
                    session = self._jobs.get(job_id)
                    if session is not None and not session["done"].is_set():
                        self._fenced.add(connection["daemon_id"])
                        session["tools"] = None
                        session["cancelling"] = True
                        session["queue"].put_nowait(
                            dict(
                                type="run.failed",
                                data=dict(
                                    error="daemon disconnected; remote cleanup unconfirmed, target fenced",
                                    code=f"{self.error_code_prefix}.daemon_disconnected",
                                    retryable=False,
                                ),
                            )
                        )
                        session["queue"].put_nowait(None)

    async def _handle_message(self, connection, raw_message):
        try:
            message = json.loads(raw_message)
        except (ValueError, TypeError):
            return
        if not isinstance(message, dict):
            return
        # Captured socket identity, never a lookup by display name.
        if self._connections.get(connection["daemon_id"]) is not connection:
            return
        connection["last_seen_at"] = time.monotonic()
        kind = message.get("type")
        if kind == "daemon.ping":
            await self._send(connection, dict(type="daemon.pong"))
            return
        session = self._jobs.get(str(message.get("job_id") or ""))
        if session is None or session["owner"] is not connection:
            return
        if kind == "run.finished":
            session["tools"] = None
            session["done"].set()
            session["queue"].put_nowait(None)
        elif kind == "run.event" and not session["cancelling"] and not session["done"].is_set():
            if isinstance(message.get("event"), dict):
                session["queue"].put_nowait(message["event"])
        elif kind == "mcp.request":
            tools = session["tools"]
            if tools is None:
                payload = jsonrpc_error(None, -32000, "Run tools revoked")
            else:
                try:
                    payload = await handle_agent_runtime_mcp_payload(tools, message.get("payload"))
                except Exception as exc:
                    payload = jsonrpc_error(None, -32000, str(exc))
            await self._send(
                connection,
                dict(
                    type="mcp.response", request_id=message.get("request_id"), job_id=session["job_id"], payload=payload
                ),
            )


class LocalMCPProxy:
    """Localhost HTTP MCP proxy that forwards requests over a daemon WebSocket."""

    def __init__(
        self,
        daemon: AgentRuntimeDaemonClient,
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
                    self._write_json(400, {"jsonrpc": "2.0", "id": None, "error": str(payload)})
                    return
                try:
                    result = proxy.daemon.request_mcp(proxy.job_id, payload, proxy.request_timeout)
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
        self._cleanup_failed = False

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
                            "protocol": "coding-relay-v1",
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
                        or ready.get("protocol") != "coding-relay-v1"
                    ):
                        raise RuntimeError(f"Unexpected daemon ready response: {ready!r}")
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
                # A replacement socket must never inherit still-running jobs.
                jobs = list(self._job_tasks.values())
                for task in jobs:
                    if not task.cancelling():
                        task.cancel()
                cleanup = asyncio.gather(*jobs, return_exceptions=True)
                interrupted = False
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        interrupted = True
                results = cleanup.result()
                self._job_tasks.clear()
                if self._cleanup_failed or any(
                    isinstance(r, BaseException) and not isinstance(r, asyncio.CancelledError) for r in results
                ):
                    raise RuntimeError("daemon cleanup failed; refusing reconnect until operator verifies quiescence")
                if interrupted:
                    raise asyncio.CancelledError
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

    def request_mcp(self, job_id: str, payload: typing.Any, timeout: float) -> typing.Any:
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
            await self.websocket.send(json.dumps(message, ensure_ascii=False, separators=(",", ":")))

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
            payload: dict[str, typing.Any] = dict(raw_payload) if isinstance(raw_payload, dict) else {}
            if not job_id:
                return
            if job_id in self._job_tasks:
                raise RuntimeError("duplicate run.start")
            task = asyncio.create_task(self._run_job_wrapper(job_id, payload))
            self._job_tasks[job_id] = task

            def drop_task(_task: asyncio.Task[None]) -> None:
                self._job_tasks.pop(job_id, None)
                if not _task.cancelled() and _task.exception() is not None:
                    self._cleanup_failed = True
                    if self.websocket is not None:
                        asyncio.create_task(
                            self.websocket.close(code=1011, reason="cleanup unconfirmed; daemon halted")
                        )

            task.add_done_callback(drop_task)
            return
        if message_type == "run.cancel":
            job_id = str(message.get("job_id") or "")
            running_task = self._job_tasks.get(job_id)
            if running_task is not None:
                if not running_task.cancelling():
                    running_task.cancel()
            return
        if message_type == "run.cleanup":
            raise RuntimeError("obsolete relay: upgrade hub and daemon together")
        if message_type == "mcp.response":
            request_id = str(message.get("request_id") or "")
            future = self._pending_mcp.pop(request_id, None)
            if future is not None and not future.done():
                future.set_result(message.get("payload"))
            return

    async def _run_job_wrapper(self, job_id, payload):
        # The inner task owns subprocess cleanup. Repeated cancel frames cannot
        # interrupt its finally block and produce a premature run.finished.
        work = asyncio.create_task(self.run_job(job_id, payload))
        cancelled = False
        try:
            await asyncio.shield(work)
        except asyncio.CancelledError:
            cancelled = True
            work.cancel()
            while not work.done():
                try:
                    await asyncio.shield(work)
                except asyncio.CancelledError:
                    pass
        except Exception:
            pass  # result below reports ordinary job failures after cleanup
        try:
            work.result()
        except asyncio.CancelledError:
            cancelled = True
        except Exception as exc:
            with contextlib.suppress(Exception):
                await self.emit_event(
                    job_id, dict(type="run.failed", data=dict(error=str(exc), code="agent_runtime.daemon_unexpected"))
                )
        # BaseException cleanup failures deliberately escape WITHOUT an ack.
        if cancelled:
            with contextlib.suppress(Exception):
                await self.emit_event(
                    job_id,
                    dict(
                        type="run.failed",
                        data=dict(error="daemon run cancelled", code="agent_runtime.daemon_cancelled"),
                    ),
                )
        with contextlib.suppress(Exception):
            await self.finish_job(job_id)

    async def _request_mcp_async(self, job_id: str, request_id: str, payload: typing.Any) -> typing.Any:
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
