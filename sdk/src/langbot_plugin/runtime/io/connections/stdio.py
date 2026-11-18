from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from langbot_plugin.runtime.io import connection
from langbot_plugin.runtime.io.connection import (
    MAX_MESSAGE_BYTES,
    MAX_MESSAGE_FRAGMENTS,
    split_utf8_chunks,
)
from langbot_plugin.entities.io.errors import ConnectionClosedError
from langbot_plugin.runtime.bounded_executor import run_blocking_with_backpressure

logger = logging.getLogger(__name__)


class StdioConnection(connection.Connection):
    """The connection for Stdio connections."""

    process: asyncio.subprocess.Process | None = None

    def __init__(
        self,
        stdout: asyncio.StreamReader,
        stdin: asyncio.StreamWriter,
        process: asyncio.subprocess.Process | None = None,
        chunk_size: int = 16 * 1024,  # 16KB chunks by default
        *,
        reserve_first_message_decode: bool = False,
        reserve_first_message_send: bool = False,
    ):
        self.stdout = stdout
        self.stdin = stdin
        self.process = process
        self.chunk_size = chunk_size
        self._first_message_control_available = reserve_first_message_decode
        self._first_message_send_inline = reserve_first_message_send
        self._send_lock = asyncio.Lock()  # 发送锁，防止并发发送冲突

        self._process_exit_task = None

    async def send(self, message: str) -> None:
        """Send message with chunking support for large data."""
        async with self._send_lock:  # 确保同一时间只有一个send操作
            inline = self._first_message_send_inline
            self._first_message_send_inline = False
            if inline:
                message_bytes = message.encode("utf-8")
            else:
                message_bytes = await run_blocking_with_backpressure(
                    message.encode,
                    "utf-8",
                )
            message_size = len(message_bytes)
            if message_size > MAX_MESSAGE_BYTES:
                raise ValueError(
                    f"Runtime message exceeds {MAX_MESSAGE_BYTES} byte limit "
                    f"({message_size} bytes). Reduce attachment size or pass files "
                    "by reference instead of inline base64."
                )
            if message_size > self.chunk_size * MAX_MESSAGE_FRAGMENTS:
                raise ValueError(
                    "Runtime message would require too many stdio fragments"
                )

            # For small messages, send directly
            if message_size <= self.chunk_size:
                try:
                    self.stdin.write(message_bytes + b"\n")
                    await self.stdin.drain()
                except Exception:
                    raise ConnectionClosedError("Connection closed during send")
                return

            # For large messages, send in chunks
            try:
                del message_bytes
                if inline:
                    chunks = split_utf8_chunks(message, self.chunk_size)
                else:
                    chunks = await run_blocking_with_backpressure(
                        split_utf8_chunks,
                        message,
                        self.chunk_size,
                    )
                # Send start marker for chunked message
                chunk_header = json.dumps(
                    {"type": "chunk_start", "total_size": message_size}
                )
                self.stdin.write(chunk_header.encode("utf-8") + b"\n")
                await self.stdin.drain()

                # Send message in chunks
                offset = 0
                for chunk_text in chunks:
                    chunk_size = len(chunk_text.encode("utf-8"))
                    chunk_msg = json.dumps(
                        {
                            "type": "chunk_data",
                            "data": chunk_text,
                            "offset": offset,
                        }
                    )
                    self.stdin.write(chunk_msg.encode("utf-8") + b"\n")
                    await self.stdin.drain()
                    offset += chunk_size
                    # Small delay to prevent overwhelming the connection
                    await asyncio.sleep(0.001)

                # Send end marker
                chunk_end = json.dumps({"type": "chunk_end"})
                self.stdin.write(chunk_end.encode("utf-8") + b"\n")
                await self.stdin.drain()

            except Exception:
                raise ConnectionClosedError("Connection closed during send")

    def _is_valid_json(self, message: str) -> bool:
        """Check if message is valid JSON."""
        try:
            json.loads(message)
            return True
        except json.JSONDecodeError:
            return False

    async def _read_single_line(self) -> str:
        """Read a single line with process monitoring."""
        if self.process is not None and self._process_exit_task is None:
            self._process_exit_task = asyncio.create_task(self.process.wait())

        read_task = asyncio.create_task(self.stdout.readline())
        tasks = [read_task]
        if self._process_exit_task is not None:
            tasks.append(self._process_exit_task)

        try:
            done, _ = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if self._process_exit_task is not None and self._process_exit_task in done:
                raise ConnectionClosedError("Connection closed")

            if read_task in done:
                s_bytes = read_task.result()
                if not s_bytes:
                    # EOF received - connection is closed
                    if self._process_exit_task is not None:
                        if self._process_exit_task.done():
                            await self._process_exit_task
                            raise ConnectionClosedError(
                                "标准输出流已关闭，子进程已退出。"
                            )
                        else:
                            raise ConnectionClosedError("标准输出流意外关闭。")
                    else:
                        # process is None but still received EOF - connection is closed
                        raise ConnectionClosedError("标准输出流已关闭。")
                try:
                    return s_bytes.decode("utf-8").strip()
                except UnicodeDecodeError:
                    logger.warning("Skipping non-UTF-8 output on stdio connection")
                    return ""

            raise ConnectionClosedError("Unexpected error in reading")
        finally:
            # If process.wait() wins, or this receive is cancelled, the pending
            # readline task must not outlive its connection.
            if not read_task.done():
                read_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await read_task

    async def receive(self) -> str:
        """Receive message with chunked message support."""
        try:
            while True:
                line = await self._read_single_line()

                if not line:
                    continue

                # Try to parse as JSON to check for chunked messages
                if line.startswith("{") and line.endswith("}"):
                    if self._is_valid_json(line):
                        try:
                            msg_data = json.loads(line)

                            # Handle chunked messages
                            if isinstance(msg_data, dict) and "type" in msg_data:
                                if msg_data["type"] == "chunk_start":
                                    use_control_join = (
                                        self._first_message_control_available
                                    )
                                    self._first_message_control_available = False
                                    # Start receiving chunked message
                                    chunks = []
                                    total_size = int(msg_data.get("total_size", -1))
                                    if not 0 <= total_size <= MAX_MESSAGE_BYTES:
                                        raise ConnectionClosedError(
                                            "Invalid runtime chunked message size"
                                        )
                                    received_size = 0
                                    fragment_count = 0

                                    while True:
                                        chunk_line = await self._read_single_line()
                                        fragment_count += 1
                                        if fragment_count > MAX_MESSAGE_FRAGMENTS:
                                            raise ConnectionClosedError(
                                                "Runtime message has too many stdio fragments"
                                            )
                                        if not chunk_line or not self._is_valid_json(
                                            chunk_line
                                        ):
                                            if chunk_line:
                                                logger.warning(
                                                    "Skipping non-JSON output on stdio connection"
                                                )
                                            continue

                                        chunk_data = json.loads(chunk_line)
                                        if not isinstance(chunk_data, dict):
                                            logger.warning(
                                                "Skipping non-object output on stdio connection"
                                            )
                                            continue
                                        if chunk_data.get("type") == "chunk_data":
                                            chunk_text = chunk_data.get("data", "")
                                            if (
                                                chunk_data.get("offset")
                                                != received_size
                                            ):
                                                raise ConnectionClosedError(
                                                    "Invalid runtime chunk offset"
                                                )
                                            received_size += len(
                                                chunk_text.encode("utf-8")
                                            )
                                            if received_size > total_size:
                                                raise ConnectionClosedError(
                                                    "Runtime chunked message exceeds declared size"
                                                )
                                            chunks.append(chunk_text)
                                        elif chunk_data.get("type") == "chunk_end":
                                            if received_size != total_size:
                                                raise ConnectionClosedError(
                                                    "Incomplete runtime chunked message"
                                                )
                                            # The first host-side frame is a
                                            # bounded protocol registration.
                                            # Join it inline so neither an
                                            # exhausted ordinary pool nor a
                                            # wedged control thread can block
                                            # transport admission. Subsequent
                                            # peer traffic stays off-loop.
                                            if use_control_join:
                                                return "".join(chunks)
                                            return await run_blocking_with_backpressure(
                                                "".join,
                                                chunks,
                                            )

                                        # Yield control periodically
                                        if len(chunks) % 50 == 0:
                                            await asyncio.sleep(0)

                                # Regular message (not chunk related)
                                elif msg_data["type"] not in [
                                    "chunk_start",
                                    "chunk_data",
                                    "chunk_end",
                                ]:
                                    self._first_message_control_available = False
                                    return line
                            else:
                                # Regular JSON message
                                self._first_message_control_available = False
                                return line
                        except (json.JSONDecodeError, KeyError):
                            # If JSON parsing fails, treat as regular message
                            self._first_message_control_available = False
                            return line
                    else:
                        logger.warning("Skipping non-JSON output on stdio connection")
                else:
                    logger.warning("Skipping non-JSON output on stdio connection")

        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            raise ConnectionClosedError("Connection closed")

    async def close(self) -> None:
        self.stdin.close()
        wait_closed = getattr(self.stdin, "wait_closed", None)
        if wait_closed is not None:
            with contextlib.suppress(Exception):
                await wait_closed()
        if self._process_exit_task is not None:
            if not self._process_exit_task.done():
                self._process_exit_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._process_exit_task
            self._process_exit_task = None
