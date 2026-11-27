"""Explicit, run-scoped streaming replies shared by code processors and runners."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class ReplyStream:
    """One reply. Updates replace the full text; they are not token deltas."""

    def __init__(self, api):
        self._api = api
        self._id = str(uuid.uuid4())
        self._text = ""
        self._closed = False
        self._lock = asyncio.Lock()
        self.result: dict | None = None

    async def _send(self, operation: str) -> dict:
        response = await self._api._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.REPLY_STREAM,
            {
                "run_id": self._api.run_id,
                "stream_id": self._id,
                "operation": operation,
                "text": self._text,
            },
            self._api._bounded_timeout(default=30.0),
        )
        self.result = self._api._expect_key(
            response, "result", PluginToRuntimeAction.REPLY_STREAM
        )
        return self.result

    async def update(self, text: str) -> dict:
        """Replace the reply with the complete text generated so far."""
        if not isinstance(text, str) or len(text) > 200_000:
            raise ValueError("Reply text must be a string of at most 200000 characters")
        async with self._lock:
            if self._closed:
                raise ValueError("Reply stream is closed")
            self._text = text
            return await self._send("update")

    async def _close(self, operation: str) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            await self._send(operation)


class AgentRunReplyStreamAPIMixin:
    @asynccontextmanager
    async def reply_stream(self) -> AsyncIterator[ReplyStream]:
        """Explicitly reply to this event, finishing on normal context exit.

        Unsupported platforms buffer updates and send once on successful exit.
        An exception cancels buffered delivery; the Host closes any visible card.
        Requires the same permission as event_reply and a Host advertising reply_stream.
        """
        self._require_context_api("reply_stream")
        self._validate_tool_access("event_reply", "call")
        stream = ReplyStream(self)
        try:
            yield stream
        except BaseException:
            try:
                await stream._close("abort")
            except Exception:
                # Host run cleanup also closes streams if the transport is unavailable.
                pass
            raise
        else:
            await stream._close("finish")
