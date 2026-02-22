"""Message Aggregator Module

This module provides message aggregation/debounce functionality.
When users send multiple messages consecutively, the aggregator will wait
for a configurable delay period and merge them into a single message
before processing.
"""

from __future__ import annotations

import asyncio
import time
import typing
from dataclasses import dataclass, field

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter

if typing.TYPE_CHECKING:
    from ..core import app


@dataclass
class PendingMessage:
    """A pending message waiting to be aggregated"""

    bot_uuid: str
    launcher_type: provider_session.LauncherTypes
    launcher_id: typing.Union[int, str]
    sender_id: typing.Union[int, str]
    message_event: platform_events.MessageEvent
    message_chain: platform_message.MessageChain
    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter
    pipeline_uuid: typing.Optional[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionBuffer:
    """Buffer for a single session's pending messages"""

    session_id: str
    messages: list[PendingMessage] = field(default_factory=list)
    timer_task: typing.Optional[asyncio.Task] = None
    last_message_time: float = field(default_factory=time.time)


class MessageAggregator:
    """Message aggregator that buffers and merges consecutive messages

    This class implements a debounce mechanism for incoming messages.
    When a message arrives, it starts a timer. If more messages arrive
    before the timer expires, they are buffered. When the timer expires,
    all buffered messages are merged and sent to the query pool.
    """

    ap: app.Application

    buffers: dict[str, SessionBuffer]
    """Session ID -> SessionBuffer mapping"""

    lock: asyncio.Lock
    """Lock for thread-safe buffer operations"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.buffers = {}
        self.lock = asyncio.Lock()

    def _get_session_id(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: typing.Union[int, str],
    ) -> str:
        """Generate a unique session ID"""
        return f'{bot_uuid}:{launcher_type.value}:{launcher_id}'

    async def _get_aggregation_config(self, pipeline_uuid: typing.Optional[str]) -> tuple[bool, float]:
        """Get aggregation configuration for a pipeline

        Returns:
            tuple: (enabled, delay_seconds)
        """
        default_enabled = True
        default_delay = 1.5

        if pipeline_uuid is None:
            return default_enabled, default_delay

        # Get pipeline from pipeline manager
        pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
        if pipeline is None:
            return default_enabled, default_delay

        config = pipeline.pipeline_entity.config or {}
        trigger_config = config.get('trigger', {})
        aggregation_config = trigger_config.get('message-aggregation', {})

        enabled = aggregation_config.get('enabled', default_enabled)
        delay = aggregation_config.get('delay', default_delay)

        # Clamp delay to valid range
        delay = max(1.0, min(10.0, float(delay)))

        return enabled, delay

    async def add_message(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: typing.Union[int, str],
        sender_id: typing.Union[int, str],
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid: typing.Optional[str] = None,
    ) -> None:
        """Add a message to the aggregation buffer

        If aggregation is disabled for the pipeline, the message is sent
        directly to the query pool. Otherwise, it's buffered and will be
        merged with other messages from the same session.
        """
        enabled, delay = await self._get_aggregation_config(pipeline_uuid)

        if not enabled:
            # Aggregation disabled, send directly to query pool
            await self.ap.query_pool.add_query(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                message_event=message_event,
                message_chain=message_chain,
                adapter=adapter,
                pipeline_uuid=pipeline_uuid,
            )
            return

        session_id = self._get_session_id(bot_uuid, launcher_type, launcher_id)

        pending_msg = PendingMessage(
            bot_uuid=bot_uuid,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=sender_id,
            message_event=message_event,
            message_chain=message_chain,
            adapter=adapter,
            pipeline_uuid=pipeline_uuid,
        )

        async with self.lock:
            if session_id in self.buffers:
                buffer = self.buffers[session_id]
                # Cancel existing timer
                if buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()
                    try:
                        await buffer.timer_task
                    except asyncio.CancelledError:
                        pass
                buffer.messages.append(pending_msg)
            else:
                buffer = SessionBuffer(
                    session_id=session_id,
                    messages=[pending_msg],
                )
                self.buffers[session_id] = buffer

            buffer.last_message_time = time.time()
            # Start new timer
            buffer.timer_task = asyncio.create_task(self._delayed_flush(session_id, delay))

    async def _delayed_flush(self, session_id: str, delay: float) -> None:
        """Wait for delay then flush the buffer"""
        try:
            await asyncio.sleep(delay)
            await self._flush_buffer(session_id)
        except asyncio.CancelledError:
            # Timer was cancelled, new message arrived
            pass

    async def _flush_buffer(self, session_id: str) -> None:
        """Flush the buffer for a session, merging all messages"""
        async with self.lock:
            buffer = self.buffers.pop(session_id, None)

        if buffer is None or not buffer.messages:
            return

        if len(buffer.messages) == 1:
            # Only one message, no need to merge
            msg = buffer.messages[0]
            await self.ap.query_pool.add_query(
                bot_uuid=msg.bot_uuid,
                launcher_type=msg.launcher_type,
                launcher_id=msg.launcher_id,
                sender_id=msg.sender_id,
                message_event=msg.message_event,
                message_chain=msg.message_chain,
                adapter=msg.adapter,
                pipeline_uuid=msg.pipeline_uuid,
            )
            return

        # Merge multiple messages
        merged_msg = self._merge_messages(buffer.messages)
        await self.ap.query_pool.add_query(
            bot_uuid=merged_msg.bot_uuid,
            launcher_type=merged_msg.launcher_type,
            launcher_id=merged_msg.launcher_id,
            sender_id=merged_msg.sender_id,
            message_event=merged_msg.message_event,
            message_chain=merged_msg.message_chain,
            adapter=merged_msg.adapter,
            pipeline_uuid=merged_msg.pipeline_uuid,
        )

    def _merge_messages(self, messages: list[PendingMessage]) -> PendingMessage:
        """Merge multiple messages into one

        The merged message uses the first message as base, and combines
        all message chains with newline separators.
        """
        if len(messages) == 1:
            return messages[0]

        base_msg = messages[0]

        # Build merged message chain
        merged_chain = platform_message.MessageChain([])

        for i, msg in enumerate(messages):
            if i > 0:
                # Add newline separator between messages
                merged_chain.append(platform_message.Plain('\n'))

            # Copy all components from this message
            for component in msg.message_chain:
                merged_chain.append(component)

        # Create merged message with updated chain
        # We need to update the message_event's message_chain as well
        merged_event = base_msg.message_event
        merged_event.message_chain = merged_chain

        return PendingMessage(
            bot_uuid=base_msg.bot_uuid,
            launcher_type=base_msg.launcher_type,
            launcher_id=base_msg.launcher_id,
            sender_id=base_msg.sender_id,
            message_event=merged_event,
            message_chain=merged_chain,
            adapter=base_msg.adapter,
            pipeline_uuid=base_msg.pipeline_uuid,
        )

    async def flush_all(self) -> None:
        """Flush all pending buffers immediately

        This is useful during shutdown to ensure no messages are lost.
        """
        async with self.lock:
            session_ids = list(self.buffers.keys())

        for session_id in session_ids:
            async with self.lock:
                buffer = self.buffers.get(session_id)
                if buffer and buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()
                    try:
                        await buffer.timer_task
                    except asyncio.CancelledError:
                        pass

            await self._flush_buffer(session_id)
