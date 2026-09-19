"""Agent run orchestrator for coordinating runner execution."""

from __future__ import annotations

import time
import contextlib
import typing

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from ...telemetry import diagnostics as diagnostics
from .reply_stream import ReplyStreamSession
from ...core import app
from ...api.http.context import ExecutionContext
from ...pipeline.pool import get_query_execution_context
from .binding_resolver import AgentBindingResolver
from .context_builder import RunnerContextBuilder, RunnerContextPayload
from .descriptor import RunnerDescriptor
from .execution_context import (
    append_mcp_resource_context_to_event,
    build_mcp_resource_context_addition,
    build_execution_query,
    prepare_execution_query,
    project_mcp_resource_config,
)
from .host_models import AgentBinding, AgentEventEnvelope
from .invoker import RunnerInvoker
from .interaction_manager import InteractionManager
from .query_bridge import QueryRunBridge
from .registry import RunnerRegistry
from .resource_builder import AgentResourceBuilder
from .platform_tools import freeze_platform_context
from .result_normalizer import AgentResultNormalizer
from .run_journal import AgentRunJournal
from .session_registry import AgentRunSessionRegistry, get_session_registry
from .state_scope import build_state_context
from ...provider.tools.loaders import skill as skill_loader


ACTIVATED_SKILL_NAMES_STATE_KEY = 'host.activated_skills'


class AgentRunOrchestrator:
    """Coordinate one Runner execution.

    The orchestrator keeps the run state machine readable and delegates
    transport, Query bridging, and persistence side effects to narrower
    collaborators.
    """

    ap: app.Application
    registry: RunnerRegistry
    context_builder: RunnerContextBuilder
    resource_builder: AgentResourceBuilder
    result_normalizer: AgentResultNormalizer
    binding_resolver: AgentBindingResolver
    query_bridge: QueryRunBridge
    invoker: RunnerInvoker
    interaction_manager: InteractionManager
    journal: AgentRunJournal
    _session_registry: AgentRunSessionRegistry

    def __init__(
        self,
        ap: app.Application,
        registry: RunnerRegistry,
    ):
        self.ap = ap
        self.registry = registry
        self.context_builder = RunnerContextBuilder(ap)
        self.resource_builder = AgentResourceBuilder(ap)
        self.result_normalizer = AgentResultNormalizer(ap)
        self.binding_resolver = AgentBindingResolver()
        self.query_bridge = QueryRunBridge(self.binding_resolver)
        self.invoker = RunnerInvoker(ap)
        self.interaction_manager = InteractionManager(ap)
        self.journal = AgentRunJournal(ap)
        self._session_registry = get_session_registry()

    @diagnostics.observe('run', 'runner.run', source='agent', stage='prepare')
    async def run(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        bound_plugins: list[str] | None = None,
        adapter_context: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run an Runner from an event-first envelope."""
        runner_id = binding.runner_id
        execution_query = adapter_context.get('_query') if adapter_context else None
        execution_context = adapter_context.get('_execution_context') if adapter_context else None
        if execution_context is None and execution_query is not None:
            execution_context = get_query_execution_context(execution_query)
        if not isinstance(execution_context, ExecutionContext):
            raise ValueError('Agent run requires a trusted ExecutionContext')
        event_workspace_id = str(event.workspace_id or '').strip()
        if event_workspace_id and event_workspace_id != execution_context.workspace_uuid:
            raise ValueError('Agent event Workspace does not match its trusted ExecutionContext')
        if not event_workspace_id:
            event = event.model_copy(update={'workspace_id': execution_context.workspace_uuid})
        descriptor = await self.registry.get(
            execution_context,
            runner_id,
            bound_plugins,
        )

        diagnostics.runner_metadata(self.ap, descriptor, binding.processor_type)
        usage = 'event' if binding.processor_type == 'event_processor' else 'agent'
        if usage not in descriptor.usages:
            raise ValueError(f'The selected Runner does not support {usage} usage')

        if execution_query is None:
            execution_query = build_execution_query(event, [])
            # Synthetic events must expose the same trusted scope as pipeline queries.
            for field_name in ('instance_uuid', 'workspace_uuid', 'placement_generation', 'query_uuid'):
                object.__setattr__(execution_query, field_name, getattr(execution_context, field_name))
            project_mcp_resource_config(execution_query, binding.runner_config)
        object.__setattr__(execution_query, '_execution_context', execution_context)

        if event.event_type == 'interaction.submitted' and binding.runner_config.get('user-id-source') in (
            'legacy-session',
            'legacy-bot',
        ):
            await self.interaction_manager.restore_legacy_identity(event, binding)

        from ...box.runner import prepare_input_files

        event = event.model_copy(deep=True)
        prepare_input_files(execution_query, event.input)
        execution_event = event
        resource_addition = await build_mcp_resource_context_addition(self.ap, execution_query)
        if resource_addition:
            execution_event = event.model_copy(deep=True)
            append_mcp_resource_context_to_event(execution_event, resource_addition)

        resources = await self.resource_builder.build_resources_from_binding(
            execution_context=execution_context,
            event=event,
            binding=binding,
            descriptor=descriptor,
        )

        context = await self.context_builder.build_context_from_event(
            event=execution_event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        session_query_id = None
        if adapter_context:
            if execution_query is not None:
                skill_loader.restore_activated_skills_from_state(
                    self.ap,
                    execution_query,
                    context.get('state', {}),
                )
            session_query_id = adapter_context.get('query_id')
            if execution_query is not None or session_query_id is not None:
                context['context']['available_apis']['prompt_get'] = True
            if 'params' in adapter_context:
                context['adapter']['extra']['params'] = adapter_context['params']

        authorized_skill_names = [
            str(skill['skill_name']) for skill in resources.get('skills', []) if skill.get('skill_name')
        ]
        prepare_execution_query(execution_query, event, authorized_skill_names)
        context['variables'] = {
            key: value
            for key, value in (execution_query.variables or {}).items()
            if isinstance(key, str) and not key.startswith('_') and isinstance(value, (str, int, float, bool))
        }
        context['variables']['query_id'] = execution_query.query_id

        state_context = build_state_context(event, binding, descriptor)
        run_id = context['run_id']
        diagnostics.annotate(run_id=run_id, stage='execute')
        context['context']['available_apis']['reply_stream'] = hasattr(PluginToRuntimeAction, 'REPLY_STREAM') and any(
            tool.get('tool_name') == 'event_reply' and tool.get('tool_type') == 'platform'
            for tool in resources.get('tools', [])
        )
        reply_streams = ReplyStreamSession(
            event,
            adapter=(adapter_context or {}).get('_delivery_adapter') or getattr(execution_query, 'adapter', None),
            source=(adapter_context or {}).get('_platform_event')
            or getattr((adapter_context or {}).get('_query'), 'message_event', None),
        )
        reply_streams.diagnostics = getattr(self.ap, 'diagnostics', None)
        available_apis = context.get('context', {}).get('available_apis')
        run_authorization = {
            'runner_id': descriptor.id,
            'binding_id': binding.binding_id,
            'processor_type': binding.processor_type,
            'processor_id': binding.processor_id,
            'plugin_identity': descriptor.get_plugin_id(),
            'resources': resources,
            'available_apis': available_apis,
            'conversation_id': event.conversation_id,
            'bot_id': event.bot_id,
            'workspace_id': event.workspace_id,
            'thread_id': event.thread_id,
            'state_policy': {
                'enable_state': binding.state_policy.enable_state,
                'state_scopes': list(binding.state_policy.state_scopes),
            },
            'state_context': state_context,
        }

        seen_sequences: set[int] = set()
        last_sequence = 0
        assistant_transcript_written = False
        terminal_status: str | None = None
        terminal_reason: str | None = None
        terminal_usage: dict[str, typing.Any] | None = None

        try:
            await self.journal.create_run(
                event=event,
                binding=binding,
                descriptor=descriptor,
                context=context,
                authorization=run_authorization,
            )
            await self._session_registry.register(
                run_id=run_id,
                runner_id=descriptor.id,
                query_id=session_query_id,
                plugin_identity=descriptor.get_plugin_id(),
                resources=resources,
                available_apis=context.get('context', {}).get('available_apis'),
                conversation_id=event.conversation_id,
                bot_id=event.bot_id,
                workspace_id=event.workspace_id,
                thread_id=event.thread_id,
                state_policy={
                    'enable_state': binding.state_policy.enable_state,
                    'state_scopes': list(binding.state_policy.state_scopes),
                },
                state_context=state_context,
                execution_query=execution_query,
                platform_context=freeze_platform_context(event),
                reply_streams=reply_streams,
            )

            event_log_id = await self.journal.write_event_log(
                event=event,
                binding=binding,
                run_id=run_id,
                runner_id=descriptor.id,
            )
            if event.event_type == 'message.received' and event.conversation_id:
                await self.journal.write_user_transcript(
                    event=event,
                    event_log_id=event_log_id,
                )

            async with contextlib.aclosing(self.invoker.invoke(descriptor, context)) as results:
                async for result_dict in results:
                    result_dict = dict(result_dict)
                    sequence = result_dict.get('sequence')
                    if sequence is not None:
                        try:
                            sequence_int = int(sequence)
                        except (TypeError, ValueError):
                            self.ap.logger.warning(
                                f'Runner {descriptor.id} returned invalid result sequence: {sequence}'
                            )
                            sequence_int = last_sequence + 1
                            result_dict['sequence'] = sequence_int
                        else:
                            if sequence_int in seen_sequences:
                                self.ap.logger.warning(
                                    f'Runner {descriptor.id} returned duplicate result sequence '
                                    f'{sequence_int} for run {run_id}; dropping duplicate'
                                )
                                continue
                            if sequence_int <= 0:
                                self.ap.logger.warning(
                                    f'Runner {descriptor.id} returned non-positive result sequence '
                                    f'{sequence_int} for run {run_id}'
                                )
                                sequence_int = last_sequence + 1
                                result_dict['sequence'] = sequence_int
                            elif last_sequence and sequence_int != last_sequence + 1:
                                self.ap.logger.warning(
                                    f'Runner {descriptor.id} result sequence gap or out-of-order '
                                    f'for run {run_id}: previous={last_sequence}, current={sequence_int}'
                                )
                            seen_sequences.add(sequence_int)
                            last_sequence = max(last_sequence, sequence_int)
                    else:
                        sequence_int = last_sequence + 1
                        result_dict['sequence'] = sequence_int
                        seen_sequences.add(sequence_int)
                        last_sequence = sequence_int

                    result_type = result_dict.get('type')
                    if result_type and not self.result_normalizer.validate_payload(
                        result_type,
                        result_dict.get('data', {}),
                        descriptor,
                    ):
                        continue

                    await self.journal.append_run_result(
                        result_dict=result_dict,
                        run_id=run_id,
                        sequence=sequence_int,
                    )

                    # Trusted Host observers receive validated events before message-only normalization.
                    result_observer = (adapter_context or {}).get('_result_observer')
                    if result_observer is not None:
                        await result_observer(result_dict)

                    if result_type == 'state.updated':
                        await self.journal.handle_state_updated_event(
                            result_dict,
                            event,
                            binding,
                            descriptor,
                            run_id=run_id,
                        )
                        await self.result_normalizer.normalize(result_dict, descriptor)
                        continue

                    if result_type == 'action.requested':
                        if await self.interaction_manager.handle_result(
                            result_dict=result_dict,
                            event=event,
                            binding=binding,
                            descriptor=descriptor,
                            run_id=run_id,
                            adapter_context=adapter_context,
                        ):
                            continue

                    if result_type == 'run.completed':
                        terminal_status = 'completed'
                        terminal_reason = (
                            result_dict.get('data', {}).get('finish_reason')
                            if isinstance(result_dict.get('data'), dict)
                            else None
                        )
                        usage = result_dict.get('usage')
                        if isinstance(usage, dict):
                            terminal_usage = usage
                    elif result_type == 'run.failed':
                        terminal_status = 'failed'
                        data = result_dict.get('data') if isinstance(result_dict.get('data'), dict) else {}
                        terminal_reason = data.get('error') or data.get('code')
                        usage = result_dict.get('usage')
                        if isinstance(usage, dict):
                            terminal_usage = usage

                    has_completed_message = result_type == 'message.completed' or (
                        result_type == 'run.completed'
                        and isinstance(result_dict.get('data'), dict)
                        and bool(result_dict['data'].get('message'))
                    )
                    if has_completed_message and event.conversation_id and not assistant_transcript_written:
                        await self.journal.write_assistant_transcript(
                            result_dict=result_dict,
                            event=event,
                            run_id=run_id,
                            runner_id=descriptor.id,
                        )
                        assistant_transcript_written = True

                    result = await self.result_normalizer.normalize(result_dict, descriptor)
                    file_ids = result_dict.get('data', {}).get('file_ids', [])
                    if file_ids:
                        if result_type != 'message.completed' or result is None:
                            raise ValueError('Files must be attached to a completed message')
                        if binding.processor_type != 'pipeline':
                            raise ValueError('Agent files must be sent explicitly through the reply API')
                        from ...box.runner import exported_message, binding_for

                        async with binding_for(execution_query).lock:
                            result.attachments = exported_message(execution_query, file_ids, consume=True)

                    if result is not None:
                        yield result

                    run_snapshot = await self.journal.get_run(run_id)
                    if run_snapshot and run_snapshot.get('cancel_requested_at') is not None:
                        terminal_status = 'cancelled'
                        terminal_reason = run_snapshot.get('status_reason') or 'cancel_requested'
                        break
            diagnostics.set_outcome(
                {'completed': 'succeeded', 'failed': 'failed', 'cancelled': 'cancelled'}.get(
                    terminal_status, 'succeeded'
                ),
                reason_code='runner_failed' if terminal_status == 'failed' else '',
            )
            await self.journal.finalize_run(
                run_id=run_id,
                status=terminal_status or 'completed',
                status_reason=terminal_reason,
                usage=terminal_usage,
            )
        except Exception as exc:
            diagnostics.set_outcome('timeout' if self._is_deadline_exhausted(context) else 'failed')
            failed_usage = terminal_usage
            await self.journal.finalize_run(
                run_id=run_id,
                status='timeout' if self._is_deadline_exhausted(context) else 'failed',
                status_reason=str(exc),
                usage=failed_usage,
            )
            raise
        finally:
            binding_box = getattr(execution_query, '_box_binding', None)
            if binding_box is not None and binding_box.run_id == run_id:
                object.__delattr__(execution_query, '_box_binding')
            session = await self._session_registry.unregister(run_id)
            await reply_streams.close()
            pending_steering = session.get('steering_queue', []) if session else []
            if pending_steering:
                try:
                    await self.journal.write_steering_dropped_audits(
                        pending_steering,
                        run_id,
                        descriptor.id,
                    )
                except Exception as exc:
                    self.ap.logger.warning(
                        f'Failed to write dropped steering audit for run {run_id}: {exc}',
                        exc_info=True,
                    )

    @diagnostics.observe('lifecycle', 'runner.query_prepare', source='pipeline', stage='prepare')
    async def run_from_query(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run an Runner from the current Pipeline Query entry point."""
        plan = self.query_bridge.build_plan(query)
        adapter_context = dict(plan.adapter_context)
        adapter_context['_query'] = query
        import copy

        adapter_context['_pipeline_expected_config'] = copy.deepcopy(query.pipeline_config)
        adapter_context['_pipeline_conversation'] = getattr(getattr(query, 'session', None), 'using_conversation', None)
        adapter_context['_execution_context'] = get_query_execution_context(query)

        async with contextlib.aclosing(
            self.run(
                plan.event,
                plan.binding,
                bound_plugins=plan.bound_plugins,
                adapter_context=adapter_context,
            )
        ) as results:
            async for result in results:
                yield result

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution."""
        return self.query_bridge.resolve_runner_id_for_telemetry(query)

    async def try_claim_steering_from_query(
        self,
        query: pipeline_query.Query,
    ) -> bool:
        """Claim a query as steering input for an active run when possible."""
        plan = self.query_bridge.build_plan(query)
        event = plan.event
        binding = plan.binding

        if event.event_type != 'message.received' or not event.conversation_id:
            return False

        descriptor = await self.registry.get(
            get_query_execution_context(query),
            binding.runner_id,
            plan.bound_plugins,
        )
        if not descriptor.supports_steering():
            return False

        target_run_id = await self._session_registry.find_steering_target(
            conversation_id=event.conversation_id,
            runner_id=descriptor.id,
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            thread_id=event.thread_id,
        )
        if target_run_id is None:
            return False

        execution_event = event
        resource_addition = await build_mcp_resource_context_addition(self.ap, query)
        if resource_addition:
            execution_event = event.model_copy(deep=True)
            append_mcp_resource_context_to_event(execution_event, resource_addition)

        steering_item = self._build_steering_item(execution_event, target_run_id, descriptor.id)
        if not await self._session_registry.enqueue_steering(target_run_id, steering_item):
            return False

        try:
            event_log_id = await self.journal.write_event_log(
                event=event,
                binding=binding,
                run_id=target_run_id,
                runner_id=descriptor.id,
                metadata={
                    'steering': {
                        'status': 'queued',
                        'trigger_behavior': 'absorbed_into_active_run',
                        'claimed_by_run_id': target_run_id,
                        'claimed_runner_id': descriptor.id,
                        'claimed_at': steering_item.get('claimed_at'),
                    },
                },
            )
            await self.journal.write_user_transcript(event, event_log_id)
        except Exception as exc:
            self.ap.logger.warning(
                f'Failed to persist steering event {event.event_id} for run {target_run_id}: {exc}',
                exc_info=True,
            )

        self.ap.logger.info(f'Claimed event {event.event_id} as steering input for run {target_run_id}')
        return True

    def _build_steering_item(
        self,
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> dict[str, typing.Any]:
        """Build the run-scoped steering item returned by the Host pull API."""
        return {
            'claimed_run_id': run_id,
            'runner_id': runner_id,
            'claimed_at': int(time.time()),
            'event': {
                'event_id': event.event_id,
                'event_type': event.event_type,
                'event_time': event.event_time,
                'source': event.source,
                'source_event_type': event.source_event_type,
                'raw_ref': event.raw_ref.model_dump(mode='json') if event.raw_ref else None,
                'data': event.data,
            },
            'conversation': {
                'conversation_id': event.conversation_id,
                'thread_id': event.thread_id,
                'bot_id': event.bot_id,
                'workspace_id': event.workspace_id,
            },
            'actor': event.actor.model_dump(mode='json') if event.actor else None,
            'subject': event.subject.model_dump(mode='json') if event.subject else None,
            'input': {
                'text': event.input.text if event.input else None,
                'contents': [
                    c.model_dump(mode='json') if hasattr(c, 'model_dump') else c
                    for c in (event.input.contents if event.input else [])
                ],
                'attachments': [
                    a.model_dump(mode='json') if hasattr(a, 'model_dump') else a
                    for a in (event.input.attachments if event.input else [])
                ],
            },
        }

    async def _invoke_runner(
        self,
        descriptor: RunnerDescriptor,
        context: RunnerContextPayload,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Compatibility delegate for older tests and internal callers."""
        async for result in self.invoker.invoke(descriptor, context):
            yield result

    async def _next_with_deadline(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: RunnerDescriptor,
        context: RunnerContextPayload,
    ) -> dict[str, typing.Any]:
        return await self.invoker._next_with_deadline(gen, descriptor, context)

    def _remaining_deadline_seconds(
        self,
        context: RunnerContextPayload,
    ) -> float | None:
        return self.invoker._remaining_deadline_seconds(context)

    def _is_deadline_exhausted(self, context: RunnerContextPayload) -> bool:
        return self.invoker._is_deadline_exhausted(context)

    async def _close_generator(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: RunnerDescriptor,
    ) -> None:
        await self.invoker._close_generator(gen, descriptor)

    async def _handle_state_updated_event(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: RunnerDescriptor,
    ) -> None:
        await self.journal.handle_state_updated_event(result_dict, event, binding, descriptor)

    async def _write_event_log(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        run_id: str,
        runner_id: str,
    ) -> str:
        return await self.journal.write_event_log(event, binding, run_id, runner_id)

    async def _write_user_transcript(
        self,
        event: AgentEventEnvelope,
        event_log_id: str,
    ) -> None:
        await self.journal.write_user_transcript(event, event_log_id)

    async def _write_assistant_transcript(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> None:
        await self.journal.write_assistant_transcript(
            result_dict=result_dict,
            event=event,
            run_id=run_id,
            runner_id=runner_id,
        )
