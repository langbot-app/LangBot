from __future__ import annotations

from typing import Callable, Coroutine, Any
import asyncio
import contextlib

from langbot_plugin.runtime.io.connections import stdio as stdio_connection
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.controller import Controller

_PROCESS_GRACEFUL_EXIT_TIMEOUT_SEC = 2.0
_PROCESS_TERMINATE_EXIT_TIMEOUT_SEC = 2.0
_PROCESS_KILL_EXIT_TIMEOUT_SEC = 2.0


async def _wait_for_process_exit(
    process: asyncio.subprocess.Process,
    timeout: float,
) -> bool:
    if process.returncode is not None:
        return True
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return process.returncode is not None
    return True


async def stop_process(process: asyncio.subprocess.Process) -> bool:
    """Reap a subprocess while preserving its opportunity for graceful cleanup."""

    if await _wait_for_process_exit(
        process,
        _PROCESS_GRACEFUL_EXIT_TIMEOUT_SEC,
    ):
        return True

    with contextlib.suppress(ProcessLookupError):
        process.terminate()
    if await _wait_for_process_exit(
        process,
        _PROCESS_TERMINATE_EXIT_TIMEOUT_SEC,
    ):
        return True

    with contextlib.suppress(ProcessLookupError):
        process.kill()
    return await _wait_for_process_exit(
        process,
        _PROCESS_KILL_EXIT_TIMEOUT_SEC,
    )


class StdioClientController(Controller):
    """The controller for stdio client."""

    process: asyncio.subprocess.Process | None = None
    connection: stdio_connection.StdioConnection | None = None

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        working_dir: str = ".",
        *,
        capture_stderr: bool = False,
        close_process_on_callback_return: bool = True,
    ):
        self.command = command
        self.args = args
        self.env = env
        self.working_dir = working_dir
        self.capture_stderr = capture_stderr
        self.close_process_on_callback_return = close_process_on_callback_return

    async def run(
        self,
        new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]],
    ):
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE if self.capture_stderr else None,
            env=self.env,
            cwd=self.working_dir,
        )

        if self.process.stdout is None or self.process.stdin is None:
            raise RuntimeError("Failed to create subprocess pipes")

        self.connection = stdio_connection.StdioConnection(
            self.process.stdout,
            self.process.stdin,
            process=self.process,
            reserve_first_message_decode=True,
            reserve_first_message_send=True,
        )
        try:
            await new_connection_callback(self.connection)
        finally:
            if self.close_process_on_callback_return:
                await self.close()

    async def close(self) -> None:
        """Close pipes and reap the owned subprocess."""
        if self.connection is not None:
            with contextlib.suppress(Exception):
                await self.connection.close()
            self.connection = None

        process = self.process
        if process is None:
            return
        self.process = None
        if process.returncode is not None:
            return

        if not await stop_process(process):
            raise RuntimeError("Stdio subprocess did not exit after SIGKILL")
