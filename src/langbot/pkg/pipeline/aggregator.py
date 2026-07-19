"""Workspace-scoped message aggregation and debounce support."""

from __future__ import annotations

import asyncio
import time
import typing
from dataclasses import dataclass, field

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from ..api.http.context import ExecutionContext
from ..core.task_boundary import create_detached_task, run_in_workspace_uow
from .pool import ExecutionContextMismatchError
from ..workspace.errors import WorkspaceError, WorkspaceInvariantError

if typing.TYPE_CHECKING:
    from ..core import app

MAX_BUFFER_MESSAGES = 10

AggregationKey = tuple[
    str,
    str,
    int,
    str,
    str | None,
    str,
    int | str,
]


@dataclass
class PendingMessage:
    """A pending message carrying its trusted execution scope."""

    execution_context: ExecutionContext
    bot_uuid: str
    launcher_type: provider_session.LauncherTypes
    launcher_id: int | str
    sender_id: int | str
    message_event: platform_events.MessageEvent
    message_chain: platform_message.MessageChain
    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter
    pipeline_uuid: str | None
    routed_by_rule: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionBuffer:
    """Pending messages for one scoped aggregation key."""

    aggregation_key: AggregationKey
    execution_context: ExecutionContext
    messages: list[PendingMessage] = field(default_factory=list)
    timer_task: asyncio.Task | None = None
    last_message_time: float = field(default_factory=time.time)


class MessageAggregator:
    """Debounce consecutive messages without crossing Workspace boundaries."""

    ap: app.Application
    buffers: dict[AggregationKey, SessionBuffer]
    lock: asyncio.Lock

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.buffers = {}
        self.lock = asyncio.Lock()

    def _get_aggregation_key(
        self,
        execution_context: ExecutionContext,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: int | str,
        pipeline_uuid: str | None,
    ) -> AggregationKey:
        """Build a key that cannot alias another Workspace, bot, or pipeline."""

        return (
            execution_context.instance_uuid,
            execution_context.workspace_uuid,
            execution_context.placement_generation,
            bot_uuid,
            pipeline_uuid,
            launcher_type.value,
            launcher_id,
        )

    async def _get_aggregation_config(
        self,
        execution_context: ExecutionContext,
        pipeline_uuid: str | None,
    ) -> tuple[bool, float]:
        """Return aggregation enablement and a clamped debounce delay."""

        default_enabled = False
        default_delay = 1.5

        if pipeline_uuid is None:
            return default_enabled, default_delay

        pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(
            execution_context,
            pipeline_uuid,
        )
        if pipeline is None:
            return default_enabled, default_delay

        config = pipeline.pipeline_entity.config or {}
        trigger_config = config.get('trigger', {})
        aggregation_config = trigger_config.get('message-aggregation', {})
        enabled = aggregation_config.get('enabled', default_enabled)

        delay_raw = aggregation_config.get('delay', default_delay)
        try:
            delay = float(delay_raw)
        except (TypeError, ValueError):
            delay = default_delay

        return enabled, max(1.0, min(10.0, delay))

    async def add_message(
        self,
        bot_uuid: str,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: int | str,
        sender_id: int | str,
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid: str | None = None,
        routed_by_rule: bool = False,
        execution_context: ExecutionContext | None = None,
    ) -> None:
        """Buffer or directly enqueue a message in its trusted Workspace."""

        execution_context = await self.ap.query_pool.resolve_execution_context(
            execution_context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
        )
        enabled, delay = await self._get_aggregation_config(execution_context, pipeline_uuid)

        if not enabled:
            await self.ap.query_pool.add_query(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_id,
                message_event=message_event,
                message_chain=message_chain,
                adapter=adapter,
                pipeline_uuid=pipeline_uuid,
                routed_by_rule=routed_by_rule,
                execution_context=execution_context,
            )
            return

        aggregation_key = self._get_aggregation_key(
            execution_context,
            bot_uuid,
            launcher_type,
            launcher_id,
            pipeline_uuid,
        )
        pending_msg = PendingMessage(
            execution_context=execution_context,
            bot_uuid=bot_uuid,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=sender_id,
            message_event=message_event,
            message_chain=message_chain,
            adapter=adapter,
            pipeline_uuid=pipeline_uuid,
            routed_by_rule=routed_by_rule,
        )

        force_flush = False
        async with self.lock:
            buffer = self.buffers.get(aggregation_key)
            if buffer is None:
                buffer = SessionBuffer(
                    aggregation_key=aggregation_key,
                    execution_context=execution_context,
                    messages=[pending_msg],
                )
                self.buffers[aggregation_key] = buffer
            else:
                if buffer.execution_context != execution_context:
                    raise ExecutionContextMismatchError('Aggregation buffer ExecutionContext changed for the same key')
                if buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()
                buffer.messages.append(pending_msg)

            buffer.last_message_time = time.time()
            if len(buffer.messages) >= MAX_BUFFER_MESSAGES:
                force_flush = True
            else:
                buffer.timer_task = create_detached_task(
                    self._delayed_flush(aggregation_key, delay, execution_context),
                    after_commit_manager=getattr(self.ap, 'persistence_mgr', None),
                )

        if force_flush:
            await self._flush_buffer(aggregation_key, execution_context)

    async def _delayed_flush(
        self,
        aggregation_key: AggregationKey,
        delay: float,
        execution_context: ExecutionContext,
    ) -> None:
        """Flush after the debounce delay using the captured context."""

        try:
            await asyncio.sleep(delay)
            await run_in_workspace_uow(
                self.ap,
                execution_context.workspace_uuid,
                lambda: self._flush_buffer(aggregation_key, execution_context),
            )
        except asyncio.CancelledError:
            pass
        except WorkspaceError as exc:
            self.ap.logger.info(
                f'Dropped an aggregated message because its Workspace execution binding is stale: {exc}'
            )

    async def _flush_buffer(
        self,
        aggregation_key: AggregationKey,
        execution_context: ExecutionContext,
    ) -> None:
        """Flush one buffer only when the captured scope still matches."""

        async with self.lock:
            buffer = self.buffers.get(aggregation_key)
            if buffer is None:
                return
            if buffer.execution_context != execution_context:
                raise ExecutionContextMismatchError('Timer ExecutionContext does not match the aggregation buffer')
            self.buffers.pop(aggregation_key)

        if not buffer.messages:
            return

        message = buffer.messages[0] if len(buffer.messages) == 1 else self._merge_messages(buffer.messages)
        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise WorkspaceInvariantError('Aggregation buffer instance does not match the active Workspace binding')
        await self.ap.query_pool.add_query(
            bot_uuid=message.bot_uuid,
            launcher_type=message.launcher_type,
            launcher_id=message.launcher_id,
            sender_id=message.sender_id,
            message_event=message.message_event,
            message_chain=message.message_chain,
            adapter=message.adapter,
            pipeline_uuid=message.pipeline_uuid,
            routed_by_rule=message.routed_by_rule,
            execution_context=message.execution_context,
        )

    def _merge_messages(self, messages: list[PendingMessage]) -> PendingMessage:
        """Merge message chains after proving all messages share one scope."""

        if not messages:
            raise ValueError('At least one pending message is required')
        if len(messages) == 1:
            return messages[0]

        base_msg = messages[0]
        base_key = self._get_aggregation_key(
            base_msg.execution_context,
            base_msg.bot_uuid,
            base_msg.launcher_type,
            base_msg.launcher_id,
            base_msg.pipeline_uuid,
        )
        for message in messages[1:]:
            message_key = self._get_aggregation_key(
                message.execution_context,
                message.bot_uuid,
                message.launcher_type,
                message.launcher_id,
                message.pipeline_uuid,
            )
            if message_key != base_key or message.execution_context != base_msg.execution_context:
                raise ExecutionContextMismatchError('Cannot merge pending messages from different execution scopes')

        merged_chain = platform_message.MessageChain([])
        for index, message in enumerate(messages):
            if index > 0:
                merged_chain.append(platform_message.Plain(text='\n'))
            for component in message.message_chain:
                merged_chain.append(component)

        return PendingMessage(
            execution_context=base_msg.execution_context,
            bot_uuid=base_msg.bot_uuid,
            launcher_type=base_msg.launcher_type,
            launcher_id=base_msg.launcher_id,
            sender_id=base_msg.sender_id,
            message_event=base_msg.message_event,
            message_chain=merged_chain,
            adapter=base_msg.adapter,
            pipeline_uuid=base_msg.pipeline_uuid,
            routed_by_rule=any(message.routed_by_rule for message in messages),
        )

    async def flush_all(self) -> None:
        """Flush all pending buffers without dropping their captured scopes."""

        async with self.lock:
            pending_buffers = [(key, buffer.execution_context) for key, buffer in self.buffers.items()]
            for buffer in self.buffers.values():
                if buffer.timer_task and not buffer.timer_task.done():
                    buffer.timer_task.cancel()

        for aggregation_key, execution_context in pending_buffers:
            try:
                await self._flush_buffer(aggregation_key, execution_context)
            except WorkspaceError as exc:
                self.ap.logger.info(
                    'Dropped an aggregated message during shutdown because its '
                    f'Workspace execution binding is stale: {exc}'
                )
