"""Process-local active Harness conversation connections."""

import asyncio
import typing


class HarnessConnectionRegistry:
    """Store authenticated sender connections by unique connection ID."""

    def __init__(self):
        self._connections: dict[str, typing.Any] = {}
        self._lock = asyncio.Lock()

    async def register(self, conversation_id: str, connection: typing.Any) -> None:
        if not conversation_id:
            raise ValueError('conversation_id is required')
        async with self._lock:
            self._connections[conversation_id] = connection

    async def unregister(self, conversation_id: str, connection: typing.Any) -> None:
        async with self._lock:
            if self._connections.get(conversation_id) is connection:
                self._connections.pop(conversation_id, None)

    async def get(self, conversation_id: str):
        async with self._lock:
            return self._connections.get(conversation_id)
