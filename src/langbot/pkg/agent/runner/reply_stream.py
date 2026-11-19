"""Host-owned explicit replies using the existing adapter streaming lifecycle."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

import pydantic
from langbot_plugin.api.entities.builtin.platform import events, message
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities import events as plugin_events
from langbot_plugin.api.entities.builtin.provider import session as provider_session


logger = logging.getLogger(__name__)


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

    def __init__(
        self, event, adapter=None, source=None, *, delivery_adapter=None, policy_query=None, agent_hooks=False
    ):
        self.adapter = adapter
        self.policy_query = policy_query
        self.agent_hooks = agent_hooks
        self._delivery_adapter_override = delivery_adapter
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

    @property
    def _delivery_adapter(self):
        return self._delivery_adapter_override if self._delivery_adapter_override is not None else self.adapter

    async def apply(self, request: ReplyStreamRequest) -> dict:
        task = asyncio.create_task(self._apply(request))
        self._active.add(task)
        try:
            return await task
        finally:
            self._active.discard(task)

    async def _responded(self, chain, *, streamed=False):
        query = self.policy_query
        if not self.agent_hooks or query is None:
            return chain
        session = query.session or provider_session.Session(
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
            bot_uuid=query.bot_uuid,
        )
        event = plugin_events.NormalMessageResponded(
            query=query,
            launcher_type=query.launcher_type.value,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
            session=session,
            prefix='',
            response_text=str(chain),
            finish_reason='stop',
            funcs_called=[],
        )
        ctx = await query._message_policy.ap.plugin_connector.emit_event(event, query._listener_plugins)
        if streamed:
            return chain
        if ctx.event.reply_message_chain is not None:
            return ctx.event.reply_message_chain
        if ctx.is_prevented_default():
            return None
        if ctx.event.response_text != event.response_text:
            return self._message(ctx.event.response_text)
        return chain

    async def prepare_reply(self, chain):
        chain = await self._responded(chain)
        if chain is not None and self.policy_query is not None:
            chain = await self.policy_query._message_policy.prepare_reply_chain(self.policy_query, chain)
        return chain

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
                prepared = False
                chain = None
                if request.operation != 'abort':
                    reply.text = request.text
                if self.mock_error:
                    raise ValueError(str(self.mock_error))
                if not self.mock and reply.text and not reply.started and request.operation != 'abort':
                    if self._delivery_adapter is None:
                        raise ValueError('This run has no platform delivery adapter')
                    # Set before I/O: an uncertain create must never be retried as another send.
                    reply.started = True
                    target_streaming = (
                        self.source is None
                        and callable(getattr(self._delivery_adapter, 'create_message_card_for_target', None))
                        and callable(getattr(self._delivery_adapter, 'reply_message_chunk_for_target', None))
                    )
                    reply.native = (
                        self.source is not None or target_streaming
                    ) and await self._delivery_adapter.is_stream_output_supported()
                    if self.policy_query is not None and request.operation == 'finish':
                        prepared = True
                        chain = await self.prepare_reply(self._message(reply.text))
                        reply.native = (
                            reply.native
                            and chain is not None
                            and len(chain) == 1
                            and isinstance(chain[0], message.Plain)
                            and not self._quote_origin
                        )
                        if reply.native:
                            reply.text = chain[0].text
                    if reply.native:
                        if self.policy_query is not None and not prepared:
                            await self.policy_query._message_policy.wait_force_delay()
                        if self.source is not None:
                            await self._delivery_adapter.create_message_card(reply.delivery_id, self.source)
                        else:
                            target_type, target_id = self.target.get('target_type'), self.target.get('target_id')
                            if not target_type or not target_id:
                                raise ValueError('This event has no reply target')
                            await self._delivery_adapter.create_message_card_for_target(
                                reply.delivery_id, str(target_type), str(target_id)
                            )
                if reply.started and reply.native:
                    await self._update_native(key, reply, final=request.operation != 'update')
                    if request.operation == 'finish' and not prepared:
                        await self._responded(self._message(reply.text), streamed=True)
                if (
                    reply.started
                    and not reply.native
                    and request.operation == 'finish'
                    and reply.text
                    and not self.mock
                ):
                    if self.source is not None:
                        if not prepared:
                            chain = await self.prepare_reply(self._message(reply.text))
                        if chain is not None:
                            await self._delivery_adapter.reply_message(
                                message_source=self.source, message=chain, quote_origin=self._quote_origin
                            )
                    else:
                        target_type, target_id = self.target.get('target_type'), self.target.get('target_id')
                        if not target_type or not target_id:
                            raise ValueError('This event has no reply target')
                        await self._delivery_adapter.send_message(
                            str(target_type), str(target_id), self._message(reply.text)
                        )
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

    @property
    def _quote_origin(self):
        return self.policy_query is not None and self.policy_query._message_policy.quote_origin

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
        if self.source is not None:
            chain = self._message(reply.text)
            if self.policy_query is not None:
                self.policy_query._message_policy.mention_sender(self.source, chain)
            await self._delivery_adapter.reply_message_chunk(
                message_source=self.source,
                bot_message=chunk,
                message=chain,
                quote_origin=self._quote_origin,
                is_final=final,
            )
        else:
            await self._delivery_adapter.reply_message_chunk_for_target(
                message_id=reply.delivery_id, content=reply.text, is_final=final
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
