# Stdio server for LangBot control connection
from __future__ import annotations

from typing import Any, BinaryIO, Callable, Coroutine
import asyncio
import sys

from langbot_plugin.runtime.io.connections import stdio as stdio_connection
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.controller import Controller

_DEFAULT_LIMIT = 64 * 1024


class _ThreadedStdioReader:
    """Read redirected Windows stdio without requiring an overlapped handle."""

    def __init__(self, stream: BinaryIO):
        self._stream = stream

    async def readline(self) -> bytes:
        return await asyncio.to_thread(self._stream.readline)


class _ThreadedStdioWriter:
    """Write redirected Windows stdio off the event loop."""

    def __init__(self, stream: BinaryIO):
        self._stream = stream
        self._pending = bytearray()
        self._closing = False

    def write(self, data: bytes) -> None:
        if self._closing:
            raise ConnectionError("stdio writer is closed")
        self._pending.extend(data)

    async def drain(self) -> None:
        if not self._pending:
            return
        data = bytes(self._pending)
        self._pending.clear()
        await asyncio.to_thread(self._write_and_flush, data)

    def _write_and_flush(self, data: bytes) -> None:
        self._stream.write(data)
        self._stream.flush()

    def close(self) -> None:
        # The process owns stdout. Closing the wrapper must not close the global
        # stream before loggers and shutdown handlers have finished.
        self._closing = True
        self._pending.clear()

    def is_closing(self) -> bool:
        return self._closing

    async def wait_closed(self) -> None:
        return None


def _binary_stream(stream: Any) -> BinaryIO:
    return getattr(stream, "buffer", stream)


async def connect_stdin_stdout(limit=_DEFAULT_LIMIT, loop=None):
    if sys.platform == "win32":
        # asyncio's ProactorEventLoop can only register overlapped pipe handles.
        # Standard handles inherited by a subprocess are ordinary anonymous
        # pipes, so connect_read_pipe/connect_write_pipe fail with WinError 6.
        # Use blocking stdio from worker threads on Windows instead.
        return (
            _ThreadedStdioReader(_binary_stream(sys.stdin)),
            _ThreadedStdioWriter(_binary_stream(sys.stdout)),
        )

    if loop is None:
        loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(limit=limit, loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    dummy = asyncio.Protocol()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)  # sets read_transport
    w_transport, _ = await loop.connect_write_pipe(lambda: dummy, sys.stdout)
    writer = asyncio.StreamWriter(w_transport, protocol, reader, loop)
    return reader, writer


class StdioServerController(Controller):
    def __init__(self, *, reserve_first_message_send: bool = False) -> None:
        self.reserve_first_message_send = reserve_first_message_send

    async def run(
        self,
        new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]],
    ):
        stdin_reader, stdout_writer = await connect_stdin_stdout()

        connection = stdio_connection.StdioConnection(
            stdin_reader,
            stdout_writer,
            reserve_first_message_send=self.reserve_first_message_send,
        )
        await new_connection_callback(connection)
