from __future__ import annotations

import websockets
import asyncio
from collections.abc import Mapping
from websockets.exceptions import ConnectionClosed as WebSocketClosed

from langbot_plugin.runtime.io import connection as io_connection
from langbot_plugin.runtime.io.connection import (
    MAX_MESSAGE_BYTES,
    MAX_MESSAGE_FRAGMENTS,
    split_utf8_chunks,
)
from langbot_plugin.entities.io.errors import ConnectionClosedError
from langbot_plugin.runtime.bounded_executor import run_blocking_with_backpressure


class WebSocketConnection(io_connection.Connection):
    """The connection for WebSocket connections."""

    def __init__(
        self,
        websocket: websockets.ServerConnection | websockets.ClientConnection,
        chunk_size: int = 64 * 1024,  # 64KB chunks by default
    ):
        self.websocket = websocket
        self.chunk_size = chunk_size
        self.request_headers: Mapping[str, str] = {}
        self._send_lock = asyncio.Lock()  # 发送锁，防止并发发送冲突

    async def send(self, message: str) -> None:
        """Send message with chunking support for large data."""
        async with self._send_lock:  # 确保同一时间只有一个send操作
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
                    "Runtime message would require too many WebSocket fragments"
                )

            # For small messages, send directly
            if message_size <= self.chunk_size:
                try:
                    await self.websocket.send(message, text=True)
                except WebSocketClosed:
                    raise ConnectionClosedError("Connection closed during send")
                return

            # For large messages, use chunking with streaming
            try:
                # Send one fragmented WebSocket message. Sending each chunk as
                # an independent message forces the receiver to guess message
                # boundaries and permits unbounded cross-message accumulation.
                del message_bytes
                chunks = await run_blocking_with_backpressure(
                    split_utf8_chunks,
                    message,
                    self.chunk_size,
                )
                await self.websocket.send(chunks)
            except WebSocketClosed:
                raise ConnectionClosedError("Connection closed during send")

    async def receive(self) -> str:
        """Receive message with streaming support and timeout protection."""
        try:
            message_chunks = []
            received_bytes = 0

            async for data in self.websocket.recv_streaming(decode=True):
                message_chunks.append(data)
                if len(message_chunks) > MAX_MESSAGE_FRAGMENTS:
                    await self.close()
                    raise ConnectionClosedError(
                        "Runtime message has too many WebSocket fragments"
                    )
                received_bytes += len(data.encode("utf-8"))
                if received_bytes > MAX_MESSAGE_BYTES:
                    await self.close()
                    raise ConnectionClosedError(
                        f"Runtime message exceeds {MAX_MESSAGE_BYTES} byte limit"
                    )
                if len(message_chunks) % 100 == 0:
                    await asyncio.sleep(0)

            # recv_streaming yields exactly one WebSocket message. JSON
            # validation belongs to Handler; never concatenate separate peer
            # messages while waiting for one that happens to parse.
            return await run_blocking_with_backpressure("".join, message_chunks)

        except WebSocketClosed:
            raise ConnectionClosedError("Connection closed")

    async def close(self) -> None:
        await self.websocket.close()
