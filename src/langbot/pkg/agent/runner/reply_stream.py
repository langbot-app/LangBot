"""Host-owned explicit replies using the existing adapter streaming lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

import pydantic
from langbot_plugin.api.entities.builtin.platform import events, message
from langbot_plugin.api.entities.builtin.provider import message as provider_message


class ReplyStreamRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra='forbid')

    stream_id: UUID
    operation: Literal['update', 'finish', 'abort']
    text: str = pydantic.Field(max_length=200_000, strict=True)


@dataclass
class _Reply:
    delivery_id: str = field(default_factory=lambda: str(uuid4()))
    text: str = ''
    started: bool = False
    native: bool = False
    final_attempted: bool = False
    sequence: int = 0
    status: str = 'open'
    result: dict | None = None


class ReplyStreamSession:
    """Ephemeral delivery state owned by one authorized run, never by plugin input."""

    def __init__(self, event, adapter=None, source=None):
        self.adapter = adapter
        self.source = source.to_legacy_event() if isinstance(source, events.MessageReceivedEvent) else source
        if not isinstance(self.source, events.MessageEvent):
            self.source = None
        self.target = dict(event.delivery.reply_target or {})
        self.mock = (
            event.delivery.surface == 'webui' and (event.delivery.platform_capabilities or {}).get('debug_mock') is True
        )
        self.mock_error = (
            ((event.delivery.platform_capabilities or {}).get('mock_options') or {})
            .get('errors', {})
            .get('event_reply')
        )
        self._replies: dict[str, _Reply] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._active: set[asyncio.Task] = set()

    async def apply(self, request: ReplyStreamRequest) -> dict:
        task = asyncio.create_task(self._apply(request))
        self._active.add(task)
        try:
            return await task
        finally:
            self._active.discard(task)

    async def _apply(self, request: ReplyStreamRequest) -> dict:
        async with self._lock:
            if self._closed:
                raise ValueError('Reply stream run has ended')
            key = str(request.stream_id)
            reply = self._replies.get(key)
            if reply is None:
                if len(self._replies) >= 16:
                    raise ValueError('A run may create at most 16 reply streams')
                reply = self._replies[key] = _Reply()
            if reply.status != 'open':
                if request.operation == 'update' or reply.status == 'failed':
                    raise ValueError('Reply stream is closed')
                return reply.result
            try:
                if request.operation != 'abort':
                    reply.text = request.text
                if self.mock_error:
                    raise ValueError(str(self.mock_error))
                if not self.mock and reply.text and not reply.started and request.operation != 'abort':
                    if self.adapter is None:
                        raise ValueError('This run has no platform delivery adapter')
                    # Set before I/O: an uncertain create must never be retried as another send.
                    reply.started = True
                    reply.native = self.source is not None and await self.adapter.is_stream_output_supported()
                    if reply.native:
                        await self.adapter.create_message_card(reply.delivery_id, self.source)
                if reply.started and reply.native:
                    await self._update_native(key, reply, final=request.operation != 'update')
                elif request.operation == 'finish' and reply.text and not self.mock:
                    if self.source is not None:
                        await self.adapter.reply_message(
                            message_source=self.source, message=self._message(reply.text), quote_origin=False
                        )
                    else:
                        target_type, target_id = self.target.get('target_type'), self.target.get('target_id')
                        if not target_type or not target_id:
                            raise ValueError('This event has no reply target')
                        await self.adapter.send_message(str(target_type), str(target_id), self._message(reply.text))
                if request.operation != 'update':
                    reply.status = 'completed' if request.operation == 'finish' else 'cancelled'
                reply.result = {
                    'stream_id': key,
                    'status': reply.status,
                    'delivery': 'simulated' if self.mock else 'streaming' if reply.native else 'buffered',
                    'mock': self.mock,
                    **({'text': reply.text} if request.operation == 'finish' else {}),
                }
                return reply.result
            except BaseException:
                reply.status = 'failed'
                raise

    @staticmethod
    def _message(text):
        return message.MessageChain([message.Plain(text=text)])

    async def _update_native(self, key, reply, *, final):
        if final:
            reply.final_attempted = True
        reply.sequence += 1
        chunk = provider_message.MessageChunk(
            role='assistant',
            content=reply.text,
            all_content=reply.text,
            resp_message_id=reply.delivery_id,
            msg_sequence=reply.sequence,
            is_final=final,
        )
        await self.adapter.reply_message_chunk(
            message_source=self.source,
            bot_message=chunk,
            message=self._message(reply.text),
            quote_origin=False,
            is_final=final,
        )

    async def close(self):
        """Close visible streams on cancellation; never send a buffered partial reply."""
        self._closed = True
        pending_requests = list(self._active)
        for task in pending_requests:
            task.cancel()
        if pending_requests:
            await asyncio.gather(*pending_requests, return_exceptions=True)
        async with self._lock:
            pending = [
                self._update_native(key, reply, final=True)
                for key, reply in self._replies.items()
                if reply.started and reply.native and not reply.final_attempted
            ]
            try:
                if pending:
                    await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=5)
            except TimeoutError:
                pass
            finally:
                self._replies.clear()
