"""Minimal Agent Client Protocol stdio client."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import typing

from pkg.runtime_support import terminate_process_group

_AUTH_ASSIGNMENT_RE = re.compile(r"(?i)(\bAuthorization\b[\"']?\s*[:=]\s*[\"']?)(?:Bearer\s+)?[^\"'\s,}\]]+")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:run[_-]?token|mcp[_-]?token|langbot_agent_mcp_token|"
    r"langbot[_-]?asset[_-]?run[_-]?token|api[_-]?key|secret|password)\b"
    r"[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}\]]+"
)


def _redact_secrets(text: str) -> str:
    redacted = _AUTH_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", str(text))
    redacted = _BEARER_RE.sub("Bearer [REDACTED]", redacted)
    return _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)


class AcpError(Exception):
    """ACP client error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "acp.error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class AcpProtocolError(AcpError):
    """ACP JSON-RPC protocol error."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        suffix = f" ({code})" if code is not None else ""
        super().__init__(
            f"{message}{suffix}",
            code="acp.protocol_error",
            retryable=False,
        )
        self.rpc_code = code


class AcpProcessError(AcpError):
    """ACP process lifecycle error."""


class AcpRequestHandle:
    """A pending ACP request."""

    def __init__(self, request_id: int, future: asyncio.Future[typing.Any]) -> None:
        self.request_id = request_id
        self.future = future

    async def wait(self, timeout: float | None = None) -> typing.Any:
        return await asyncio.wait_for(self.future, timeout=timeout)


class AcpStdioClient:
    """Line-delimited JSON-RPC client for ACP stdio agents."""

    def __init__(
        self,
        *,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        unset_env: typing.Sequence[str] | None = None,
        permission_decision: str = "allow_once",
        startup_timeout: float = 30.0,
        stderr_limit: int = 20000,
    ) -> None:
        self.command = command
        self.args = list(args or [])
        self.cwd = cwd
        self.env = dict(env or {})
        self.unset_env = tuple(str(name) for name in (unset_env or ()))
        self.permission_decision = permission_decision
        self.startup_timeout = startup_timeout
        self.stderr_limit = stderr_limit
        self.process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[typing.Any]] = {}
        self._updates: asyncio.Queue[dict[str, typing.Any]] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr = ""
        self._closed = False

    @property
    def stderr_tail(self) -> str:
        return _redact_secrets(self._stderr[-self.stderr_limit :])

    async def __aenter__(self) -> AcpStdioClient:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: typing.Any,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self.process is not None:
            return

        process_env = os.environ.copy()
        process_env.update(self.env)
        for name in self.unset_env:
            process_env.pop(name, None)

        try:
            self.process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    self.command,
                    *self.args,
                    cwd=self.cwd,
                    env=process_env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=os.name != "nt",
                ),
                timeout=self.startup_timeout,
            )
        except FileNotFoundError as exc:
            raise AcpProcessError(
                f"ACP command not found: {self.command}",
                code="acp.command_not_found",
            ) from exc
        except TimeoutError as exc:
            raise AcpProcessError(
                f"Timed out starting ACP command: {self.command}",
                code="acp.start_timeout",
                retryable=True,
            ) from exc

        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        process = self.process
        if process is not None:
            if os.name == "nt":
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except TimeoutError:
                        process.kill()
                        await process.wait()
            else:
                await self._close_posix_process_group(process)

        for task in (self._reader_task, self._stderr_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _close_posix_process_group(self, process: asyncio.subprocess.Process) -> None:
        await terminate_process_group(process)

    async def initialize(self, timeout: float | None = None) -> dict[str, typing.Any]:
        result = await self.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {
                        "readTextFile": False,
                        "writeTextFile": False,
                    },
                    "terminal": False,
                },
                "clientInfo": {
                    "name": "langbot-acp-agent-runner",
                    "title": "LangBot ACP Runner",
                    "version": "0.1.0",
                },
            },
            timeout=timeout,
        )
        if not isinstance(result, dict):
            raise AcpProtocolError("initialize response must be an object")
        return result

    async def request(
        self,
        method: str,
        params: dict[str, typing.Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> typing.Any:
        handle = self.send_request(method, params or {})
        return await handle.wait(timeout=timeout)

    def send_request(
        self,
        method: str,
        params: dict[str, typing.Any] | None = None,
    ) -> AcpRequestHandle:
        if self.process is None or self.process.stdin is None:
            raise AcpProcessError("ACP process is not started", code="acp.not_started")
        if self.process.returncode is not None:
            raise AcpProcessError(
                self._process_exit_message(),
                code="acp.process_exited",
                retryable=True,
            )

        request_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[typing.Any] = loop.create_future()
        self._pending[request_id] = future
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        return AcpRequestHandle(request_id, future)

    async def next_update(self, timeout: float | None = None) -> dict[str, typing.Any] | None:
        try:
            return await asyncio.wait_for(self._updates.get(), timeout=timeout)
        except TimeoutError:
            return None

    def next_update_nowait(self) -> dict[str, typing.Any] | None:
        try:
            return self._updates.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def drain_updates(self) -> None:
        while not self._updates.empty():
            self._updates.get_nowait()

    def _write(self, message: dict[str, typing.Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise AcpProcessError("ACP process is not started", code="acp.not_started")
        data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).replace("\n", "\\n")
        self.process.stdin.write(data.encode("utf-8") + b"\n")

    async def _read_stdout(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None

        while True:
            raw_line = await self.process.stdout.readline()
            if not raw_line:
                self._fail_pending(AcpProcessError(self._process_exit_message(), code="acp.process_exited"))
                return
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                self._fail_pending(AcpProtocolError(f"ACP agent wrote invalid JSON to stdout: {exc}"))
                return
            if not isinstance(message, dict):
                self._fail_pending(AcpProtocolError("ACP stdout message must be an object"))
                return
            await self._handle_message(message)

    async def _read_stderr(self) -> None:
        assert self.process is not None
        assert self.process.stderr is not None
        while True:
            chunk = await self.process.stderr.read(4096)
            if not chunk:
                return
            self._stderr += chunk.decode("utf-8", errors="replace")
            if len(self._stderr) > self.stderr_limit * 2:
                self._stderr = self._stderr[-self.stderr_limit :]

    async def _handle_message(self, message: dict[str, typing.Any]) -> None:
        if "id" in message and ("result" in message or "error" in message):
            self._handle_response(message)
            return

        method = str(message.get("method") or "")
        params = message.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        if method == "session/update":
            await self._updates.put(params)
            return

        if method == "session/request_permission":
            self._handle_request_permission(message, params)
            return

        if method.startswith("fs/") or method.startswith("terminal/"):
            self._reply_error(message.get("id"), -32601, f"Client method is not available: {method}")
            return

        if "id" in message:
            self._reply_error(message.get("id"), -32601, f"Method not found: {method}")

    def _handle_response(self, message: dict[str, typing.Any]) -> None:
        request_id = message.get("id")
        if not isinstance(request_id, int):
            return
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return

        if "error" in message:
            error = message.get("error")
            if isinstance(error, dict):
                future.set_exception(
                    AcpProtocolError(
                        str(error.get("message") or "ACP request failed"),
                        code=typing.cast(int | None, error.get("code")),
                    )
                )
            else:
                future.set_exception(AcpProtocolError("ACP request failed"))
            return

        future.set_result(message.get("result"))

    def _handle_request_permission(
        self,
        message: dict[str, typing.Any],
        params: dict[str, typing.Any],
    ) -> None:
        options = params.get("options") or []
        selected_option_id = self._select_permission_option(options)
        if selected_option_id:
            result = {"outcome": {"outcome": "selected", "optionId": selected_option_id}}
        else:
            result = {"outcome": {"outcome": "cancelled"}}
        self._reply_result(message.get("id"), result)

    def _select_permission_option(self, options: typing.Any) -> str | None:
        if not isinstance(options, list):
            return None
        preferred = self.permission_decision
        fallback: str | None = None
        for option in options:
            if not isinstance(option, dict):
                continue
            option_id = str(option.get("optionId") or "")
            kind = str(option.get("kind") or "")
            if not option_id:
                continue
            if fallback is None:
                fallback = option_id
            if kind == preferred or option_id == preferred:
                return option_id
        return fallback if preferred == "first" else None

    def _reply_result(self, request_id: typing.Any, result: dict[str, typing.Any]) -> None:
        if request_id is None:
            return
        self._write({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _reply_error(self, request_id: typing.Any, code: int, message: str) -> None:
        if request_id is None:
            return
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": code,
                    "message": message,
                },
            }
        )

    def _fail_pending(self, error: BaseException) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()

    def _process_exit_message(self) -> str:
        process = self.process
        returncode = None if process is None else process.returncode
        stderr = self.stderr_tail.strip()
        if stderr:
            return f"ACP process exited with code {returncode}: {stderr}"
        return f"ACP process exited with code {returncode}"
