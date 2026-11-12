"""Agent run orchestrator for coordinating runner execution."""

from __future__ import annotations

import time
import asyncio
import contextlib
import re
import copy
import dataclasses
import uuid
import typing
from uuid import uuid4

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.provider import prompt as provider_prompt
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from .reply_stream import ReplyStreamRequest, ReplyStreamSession
from ...core import app
from ...i18n import t
from ...i18n.workspace import get_workspace_language
from ...api.http.context import ExecutionContext
from ...pipeline.pool import get_query_execution_context
from .binding_resolver import AgentBindingResolver
from .context_builder import RunnerContextBuilder, RunnerContextPayload
from .descriptor import RunnerDescriptor
from .config_schema import extract_prompt_config
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
from .platform_tools import PLATFORM_TOOLS_BY_NAME, freeze_platform_context
from .result_normalizer import AgentResultNormalizer
from .run_journal import AgentRunJournal
from .run_ledger_store import TerminalRunTransitionError
from .session_registry import AgentRunSessionRegistry, get_session_registry
from .state_scope import build_state_context
from ...provider.tools.loaders import skill as skill_loader
from ...telemetry import resources as telemetry_resources
from ...telemetry import trace as trace_mod
from ...telemetry.execution import bind_trace as bind_execution_trace
from ...telemetry.execution import close_trace as close_execution_trace
from ...telemetry.execution import record as record_execution


def _visible_auto_reply_text(content: str) -> str:
    visible = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.IGNORECASE | re.DOTALL)
    for size in range(min(7, len(visible)), 0, -1):
        if any(tag.startswith(visible[-size:].lower()) for tag in ('<think>', '</think>')):
            return visible[:-size]
    return visible


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

    async def run(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        bound_plugins: list[str] | None = None,
        adapter_context: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        context = (adapter_context or {}).get('_execution_context')
        query = (adapter_context or {}).get('_query')
        if context is None and query is not None:
            context = get_query_execution_context(query)
        if not isinstance(context, ExecutionContext):
            raise ValueError('Agent run requires a trusted ExecutionContext')
        if not context.query_uuid:
            context = dataclasses.replace(context, query_uuid=getattr(query, 'query_uuid', None) or str(uuid.uuid4()))
            if query is not None:
                object.__setattr__(query, 'query_uuid', context.query_uuid)
        selection = await self.ap.box_service.resolve_workspace_selection(context)
        backend = selection['backend']
        adapter_context = {
            **(adapter_context or {}),
            '_execution_context': context,
            '_sandbox_backend': backend,
            '_sandbox_e2b_config': selection['e2b'],
            '_sandbox_limits': selection.get('limits', {}),
        }
        mcp_loader = getattr(getattr(self.ap, 'tool_mgr', None), 'mcp_tool_loader', None)
        async with contextlib.AsyncExitStack() as stack:
            if mcp_loader is not None:
                tool_names = (
                    None
                    if binding.resource_policy.allow_all_tools or binding.runner_config.get('mcp-resources')
                    else (binding.resource_policy.allowed_tool_names or [])
                )
                adapter_context['_sandbox_mcp_sessions'] = await stack.enter_async_context(
                    mcp_loader.task_sandbox_scope(
                        context,
                        backend,
                        tool_names=tool_names,
                        **({'limits_selection': selection['limits']} if selection.get('limits') else {}),
                        **({'e2b_selection': selection['e2b']} if backend == 'e2b' else {}),
                    )
                )
            stream = self._run(event, binding, bound_plugins, adapter_context)
            try:
                async for item in stream:
                    yield item
            finally:
                await stream.aclose()

    async def _run(
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
        usage = 'event' if binding.processor_type == 'event_processor' else 'agent'
        if usage not in descriptor.usages:
            raise ValueError(f'The selected Runner does not support {usage} usage')

        if execution_query is None:
            execution_query = build_execution_query(event, [], execution_context)
            # Event runs bypass pipeline prompt preparation, just like debug runs.
            prompt_config = extract_prompt_config(descriptor, binding.runner_config, [])
            execution_query.prompt = provider_prompt.Prompt(
                name='default',
                messages=[provider_message.Message(**item) for item in copy.deepcopy(prompt_config)],
            )
            project_mcp_resource_config(execution_query, binding.runner_config)
        object.__setattr__(execution_query, '_execution_context', execution_context)
        object.__setattr__(execution_query, '_sandbox_backend', adapter_context.get('_sandbox_backend'))
        object.__setattr__(execution_query, '_sandbox_e2b_config', adapter_context.get('_sandbox_e2b_config', {}))
        object.__setattr__(execution_query, '_sandbox_limits', adapter_context.get('_sandbox_limits', {}))
        object.__setattr__(execution_query, '_sandbox_mcp_sessions', adapter_context.get('_sandbox_mcp_sessions'))

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
            tool_catalog=getattr(execution_query, '_host_tool_catalog', None),
        )
        # Telemetry: report what this run was granted (never what it used). The
        # materialized resource list is authoritative for tools/skills/models;
        # the Runner's own config form is authoritative for its selectors.
        try:
            from . import config_schema as runner_config_schema

            capabilities = getattr(descriptor, 'capabilities', None)
            telemetry_resources.note_agent(
                runner_id=descriptor.id,
                resources=resources,
                selectors=runner_config_schema.extract_selected_resources(descriptor, binding.runner_config),
                capabilities=capabilities.model_dump() if hasattr(capabilities, 'model_dump') else None,
                tools_all=getattr(binding.resource_policy, 'allow_all_tools', None),
            )
        except Exception:
            pass

        context = await self.context_builder.build_context_from_event(
            execution_context=execution_context,
            event=execution_event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )
        recovery = (adapter_context or {}).get('_recovery')
        if recovery:
            context['run_id'] = recovery['run_id']
            context['runtime'].setdefault('metadata', {})['recovery'] = recovery['request']

        authorized_skill_names = [
            str(skill['skill_name']) for skill in resources.get('skills', []) if skill.get('skill_name')
        ]
        # Every invocation owns a new run; conversation state is not a recovery snapshot.
        prepare_execution_query(execution_query, event, authorized_skill_names)
        execution_query.variables.pop(skill_loader.ACTIVATED_SKILLS_KEY, None)

        session_query_id = None
        if adapter_context:
            session_query_id = adapter_context.get('query_id')
            if execution_query is not None or session_query_id is not None:
                context['context']['available_apis']['prompt_get'] = True
            if 'params' in adapter_context:
                context['adapter']['extra']['params'] = adapter_context['params']

        context['variables'] = {
            key: value
            for key, value in (execution_query.variables or {}).items()
            if isinstance(key, str) and not key.startswith('_') and isinstance(value, (str, int, float, bool))
        }
        context['variables']['query_id'] = execution_query.query_id

        state_context = build_state_context(event, binding, descriptor)
        run_id = context['run_id']

        # Monitoring attributes every call to the processor that ran it and to the
        # record that owns it; a Runner has to claim both itself, since no
        # Pipeline did. Runs before the Runner is invoked and before the run
        # context is handed to it, so its own variables stay private.
        from ...pipeline import monitoring_helper

        await monitoring_helper.prepare_monitoring_identity(
            self.ap,
            execution_query,
            processor_type=binding.processor_type,
            processor_id=binding.processor_id,
            runner_id=binding.runner_id,
            execution_record_id=run_id,
        )
        context['context']['available_apis']['reply_stream'] = hasattr(PluginToRuntimeAction, 'REPLY_STREAM') and any(
            tool.get('tool_name') == 'event_reply' and tool.get('tool_type') == 'platform'
            for tool in resources.get('tools', [])
        )
        reply_streams = ReplyStreamSession(
            event,
            adapter=(adapter_context or {}).get('_delivery_adapter') or getattr(execution_query, 'adapter', None),
            source=(adapter_context or {}).get('_platform_event')
            or getattr((adapter_context or {}).get('_query'), 'message_event', None),
            delivery_adapter=(adapter_context or {}).get('_recovery_delivery_adapter'),
        )
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
        execution_outcome = 'unknown'
        execution_error = ''
        auto_reply_enabled = (
            binding.processor_type == 'agent'
            and binding.delivery_policy.enable_reply
            and event.event_type == 'message.received'
            and reply_streams.adapter is not None
        )
        auto_reply_stream_id = uuid4()
        auto_reply_stream_text = ''
        auto_reply_stream_open = False
        auto_reply_cumulative_text = ''
        auto_reply_prefix = ''
        auto_reply_deferred = False
        explicit_event_reply_sent = False
        explicit_reply_text: str | None = None
        pending_explicit_replies: dict[str, str] = {}
        # A run reached without a platform ingress (WebUI debug, service API)
        # owns its own chain; a run inside an ingress reuses that chain.
        trace_binding: trace_mod.TraceBinding | None = None
        run_token: typing.Any = None
        # Workflow step node for this run; '' until the step scope is opened.
        node = ''

        try:
            trace_binding = bind_execution_trace(self.ap, run_id)
            run_token = trace_mod.set_run(run_id)
            await self.journal.create_run(
                event=event,
                binding=binding,
                descriptor=descriptor,
                context=context,
                authorization=run_authorization,
            )
            if recovery:
                await self.journal._get_run_ledger_store().authorize_recovery_run(
                    run_id,
                    authorization={
                        **run_authorization,
                        'recovery_event': self.journal._sanitize_event_data(event.model_dump(mode='json')),
                        'recovery_checkpoint': recovery['request']['events'],
                    },
                    deadline_at=context.get('runtime', {}).get('deadline_at'),
                )
            monitoring_id = (execution_query.variables or {}).get('_monitoring_message_id')
            if monitoring_id and monitoring_id != run_id:
                await self.ap.monitoring_service.link_execution_message(
                    get_query_execution_context(execution_query), monitoring_id, run_id, event.event_id
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
                actor_id=getattr(getattr(event, 'actor', None), 'actor_id', None),
                state_policy={
                    'enable_state': binding.state_policy.enable_state,
                    'state_scopes': list(binding.state_policy.state_scopes),
                },
                state_context=state_context,
                execution_query=execution_query,
                platform_context=freeze_platform_context(event),
                reply_streams=reply_streams,
                binding_id=binding.binding_id,
                processor_type=binding.processor_type,
                processor_id=binding.processor_id or binding.agent_id,
                trigger_actor=event.actor.actor_id if event.actor else None,
                interactions_enabled=binding.delivery_policy.enable_interactions,
                interactions_authorized=(
                    bool(getattr(descriptor.capabilities, 'interactions', False))
                    and 'request' in (getattr(descriptor.permissions, 'interactions', []) or [])
                ),
                runtime_context=context.get('runtime'),
            )
            recovered_steering = await self._load_recoverable_steering(
                event=event,
                descriptor=descriptor,
                run_id=run_id,
                binding=binding,
            )
            if recovered_steering:
                restored = await self._session_registry.restore_steering(run_id, recovered_steering)
                if restored:
                    self.ap.logger.info(f'Restored {restored} unacknowledged steering input(s) for run {run_id}')

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

            with trace_mod.stage_scope() as node:
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

                        usage = result_dict.get('usage')
                        if isinstance(usage, dict):
                            # Runners may emit cumulative usage snapshots on
                            # progress or message events. Keep the latest
                            # snapshot for cancellation, timeout, and
                            # disconnect finalization.
                            terminal_usage = usage

                        if result_type == 'tool.call.started':
                            result_data = result_dict.get('data') or {}
                            tool_definition = PLATFORM_TOOLS_BY_NAME.get(result_data.get('tool_name'))
                            parameters = result_data.get('parameters') or {}
                            if tool_definition is not None and tool_definition.api == 'send_message':
                                text = parameters.get('text') if isinstance(parameters, dict) else None
                                if isinstance(text, str):
                                    pending_explicit_replies[str(result_data.get('tool_call_id') or '')] = text

                        if result_type == 'tool.call.completed' and auto_reply_enabled:
                            if auto_reply_stream_open:
                                await reply_streams.apply(
                                    ReplyStreamRequest(
                                        stream_id=auto_reply_stream_id,
                                        operation='finish',
                                        text=auto_reply_stream_text,
                                    )
                                )
                            auto_reply_prefix = auto_reply_cumulative_text
                            auto_reply_stream_id = uuid4()
                            auto_reply_stream_text = ''
                            auto_reply_stream_open = False
                            result_data = result_dict.get('data') or {}
                            tool_definition = PLATFORM_TOOLS_BY_NAME.get(result_data.get('tool_name'))
                            auto_reply_deferred = (
                                tool_definition is not None
                                and tool_definition.api == 'send_message'
                                and not result_data.get('error')
                            )
                            if auto_reply_deferred and result_data.get('tool_name') == 'event_reply':
                                explicit_event_reply_sent = True
                            explicit_reply_text = pending_explicit_replies.pop(
                                str(result_data.get('tool_call_id') or ''), None
                            )

                        self.result_normalizer.annotate_result_size(result_dict, descriptor)
                        journal_started = time.monotonic()
                        await self.journal.append_run_result(
                            result_dict=result_dict,
                            run_id=run_id,
                            sequence=sequence_int,
                        )
                        journal_ms = (time.monotonic() - journal_started) * 1000

                        # Trusted Host observers receive validated events before message-only normalization.
                        result_observer = (adapter_context or {}).get('_result_observer')
                        observer_started = time.monotonic()
                        if result_observer is not None:
                            await result_observer(result_dict)
                        observer_ms = (time.monotonic() - observer_started) * 1000
                        if journal_ms + observer_ms >= 100:
                            self.ap.logger.debug(
                                f'Slow runner event consumer run={run_id} type={result_type} '
                                f'journal_ms={journal_ms:.1f} observer_ms={observer_ms:.1f}'
                            )

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

                        if result_type == 'run.completed':
                            terminal_status = 'completed'
                            terminal_reason = (
                                result_dict.get('data', {}).get('finish_reason')
                                if isinstance(result_dict.get('data'), dict)
                                else None
                            )
                        elif result_type == 'run.failed':
                            data = result_dict.get('data') if isinstance(result_dict.get('data'), dict) else {}
                            terminal_status = 'cancelled' if data.get('code') == 'cancelled' else 'failed'
                            terminal_reason = data.get('error') or data.get('code')
                        elif result_type == 'run.cancelled':
                            data = result_dict.get('data') if isinstance(result_dict.get('data'), dict) else {}
                            terminal_status = 'cancelled'
                            terminal_reason = data.get('reason') or 'runner_cancelled'

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

                        if auto_reply_enabled and not explicit_event_reply_sent and result is not None:
                            if result_type == 'message.delta' and isinstance(result, provider_message.MessageChunk):
                                cumulative_text = result.all_content or result.content
                                if isinstance(cumulative_text, str):
                                    reply_text = _visible_auto_reply_text(cumulative_text)
                                    if auto_reply_prefix and cumulative_text.startswith(auto_reply_prefix):
                                        visible_prefix = _visible_auto_reply_text(auto_reply_prefix)
                                        if reply_text.startswith(visible_prefix):
                                            reply_text = reply_text[len(visible_prefix) :]
                                    else:
                                        auto_reply_prefix = ''
                                    auto_reply_cumulative_text = cumulative_text
                                    auto_reply_stream_text = reply_text
                                    if reply_text.strip() and not auto_reply_deferred:
                                        await reply_streams.apply(
                                            ReplyStreamRequest(
                                                stream_id=auto_reply_stream_id,
                                                operation='update',
                                                text=reply_text,
                                            )
                                        )
                                        auto_reply_stream_open = True
                            elif has_completed_message:
                                reply_text = result.content
                                if isinstance(reply_text, str):
                                    reply_text = _visible_auto_reply_text(reply_text)
                                    if auto_reply_prefix and result.content.startswith(auto_reply_prefix):
                                        visible_prefix = _visible_auto_reply_text(auto_reply_prefix)
                                        if reply_text.startswith(visible_prefix):
                                            reply_text = reply_text[len(visible_prefix) :]
                                    if reply_text.strip() and (
                                        not auto_reply_deferred
                                        or explicit_reply_text is None
                                        or reply_text.strip() != explicit_reply_text.strip()
                                    ):
                                        await reply_streams.apply(
                                            ReplyStreamRequest(
                                                stream_id=auto_reply_stream_id,
                                                operation='finish',
                                                text=reply_text,
                                            )
                                        )
                                auto_reply_stream_id = uuid4()
                                auto_reply_stream_text = ''
                                auto_reply_stream_open = False
                                auto_reply_prefix = auto_reply_cumulative_text
                                auto_reply_deferred = False
                                explicit_reply_text = None

                        if auto_reply_enabled and result_type == 'run.completed' and auto_reply_stream_open:
                            await reply_streams.apply(
                                ReplyStreamRequest(
                                    stream_id=auto_reply_stream_id,
                                    operation='finish',
                                    text=auto_reply_stream_text,
                                )
                            )
                            auto_reply_stream_open = False

                        if result is not None:
                            yield result

                        run_snapshot = await self.journal.get_run(run_id)
                        if (
                            terminal_status is None
                            and run_snapshot
                            and run_snapshot.get('cancel_requested_at') is not None
                        ):
                            terminal_status = 'cancelled'
                            terminal_reason = run_snapshot.get('status_reason') or 'cancel_requested'
                            # The Host closes the stream here, so it owns the missing terminal event.
                            cancelled_result = {
                                'type': 'run.failed',
                                'run_id': run_id,
                                'sequence': last_sequence + 1,
                                'data': {
                                    'code': 'cancelled',
                                    'error': t(
                                        'Task was cancelled',
                                        locale=await get_workspace_language(self.ap, execution_context.workspace_uuid),
                                    ),
                                    'retryable': False,
                                },
                            }
                            cancelled_event = await self.journal.append_run_result(
                                result_dict=cancelled_result,
                                run_id=run_id,
                                sequence=None,
                                source='host',
                            )
                            cancelled_result['sequence'] = cancelled_event['sequence']
                            if result_observer is not None:
                                await result_observer(cancelled_result)
                            await self.result_normalizer.normalize(cancelled_result, descriptor)
            finalized = await self._finalize_run(
                run_id=run_id,
                status=terminal_status or 'completed',
                status_reason=terminal_reason,
                usage=terminal_usage,
            )
            ledger_status = finalized.get('status') if isinstance(finalized, dict) else None
            if isinstance(ledger_status, str) and ledger_status != (terminal_status or 'completed'):
                # Another writer finished the run first; report what the run
                # ledger holds instead of the status this stream would have set.
                terminal_status = ledger_status
                terminal_reason = finalized.get('status_reason') or terminal_reason
            execution_outcome = {
                'completed': 'success',
                'failed': 'failed',
                'cancelled': 'cancelled',
                'timeout': 'timeout',
            }.get(terminal_status or '', 'unknown')
            execution_error = '' if execution_outcome == 'success' else (terminal_reason or execution_outcome)
        except (asyncio.CancelledError, GeneratorExit):
            execution_outcome = 'cancelled'
            execution_error = 'cancelled'
            await self._finalize_run(
                run_id=run_id,
                status='cancelled',
                status_reason='consumer_cancelled',
                usage=terminal_usage,
            )
            raise
        except Exception as exc:
            execution_outcome = (
                'cancelled'
                if terminal_status == 'cancelled'
                else 'timeout'
                if self._is_deadline_exhausted(context)
                else 'failed'
            )
            # A chain that broke must always carry a reason, even for a bare exception.
            from ...telemetry.execution import describe_exception

            execution_error = describe_exception(exc)
            failed_usage = terminal_usage
            await self._finalize_run(
                run_id=run_id,
                status=execution_outcome,
                status_reason=terminal_reason if execution_outcome == 'cancelled' else str(exc),
                usage=failed_usage,
            )
            raise
        finally:
            record_execution(
                self.ap,
                execution_context,
                family='runner',
                operation='execute',
                mode=binding.processor_type,
                runner=descriptor.id,
                outcome=execution_outcome,
                synthetic=event.source == 'webui',
                error=execution_error,
                node=node,
            )
            self._note_runner_on_trace(descriptor.id, binding)
            trace_mod.reset_run(run_token)
            if trace_binding is not None and trace_mod.unbind_root(trace_binding):
                close_execution_trace(self.ap, trace_binding.state, 'completed')
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

    @staticmethod
    def _note_runner_on_trace(runner_id: str, binding) -> None:
        """Attach the Runner identity to the execution chain this run belongs to."""
        try:
            from ...telemetry import trace as trace_mod
            from ...utils import runner as runner_utils

            state = trace_mod.current()
            if state is None or state.closed:
                return
            state.runner = state.runner or (runner_id or '')
            if not state.runner_category:
                state.runner_category = runner_utils.get_telemetry_runner_category(
                    runner_id, getattr(binding, 'runner_config', None)
                )
        except Exception:
            pass

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution."""
        return self.query_bridge.resolve_runner_id_for_telemetry(query)

    async def cancel_active_from_query(
        self,
        query: pipeline_query.Query,
        *,
        allow_other_actors: bool = False,
    ) -> str | None:
        """Request cancellation and stop the active Runner task for this Query conversation."""

        plan = self.query_bridge.build_plan(query)
        event = plan.event
        binding = plan.binding
        if event.event_type != 'message.received' or not event.conversation_id:
            return None
        descriptor = await self.registry.get(
            get_query_execution_context(query),
            binding.runner_id,
            plan.bound_plugins,
        )
        actor = getattr(event, 'actor', None)
        actor_id = getattr(actor, 'actor_id', None)
        if not allow_other_actors and not actor_id:
            return None
        target_run_id = await self._session_registry.find_active_target(
            conversation_id=event.conversation_id,
            runner_id=descriptor.id,
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            thread_id=event.thread_id,
            actor_id=None if allow_other_actors else actor_id,
        )
        if target_run_id is None and not allow_other_actors:
            other_actor_run_id = await self._session_registry.find_active_target(
                conversation_id=event.conversation_id,
                runner_id=descriptor.id,
                bot_id=event.bot_id,
                workspace_id=event.workspace_id,
                thread_id=event.thread_id,
            )
            if other_actor_run_id is not None:
                query.variables['_stop_command_denied'] = True
        if target_run_id is None:
            return None
        if not await self._session_registry.cancel_task(target_run_id, reason='stop_command'):
            return None
        from .run_ledger_store import RunLedgerStore

        store = RunLedgerStore(self.ap.persistence_mgr.get_db_engine())
        await store.request_cancel(
            run_id=target_run_id,
            status_reason='cancelled by stop command',
        )
        return target_run_id

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

        return await self._enqueue_steering(event, execution_event, binding, target_run_id, descriptor.id)

    async def try_claim_steering_from_event(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        execution_context: ExecutionContext,
    ) -> bool:
        """Route a new platform message to an Agent waiting for interaction."""
        if event.event_type != 'message.received' or not event.conversation_id:
            return False
        waiting_run_ids = self.interaction_manager.waiting_run_ids()
        if not waiting_run_ids:
            return False
        descriptor = await self.registry.get(execution_context, binding.runner_id)
        if not descriptor.supports_steering():
            return False
        target_run_id = await self._session_registry.find_steering_target(
            conversation_id=event.conversation_id,
            runner_id=descriptor.id,
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            thread_id=event.thread_id,
            binding_id=binding.binding_id,
            eligible_run_ids=waiting_run_ids,
        )
        if target_run_id is None:
            return False
        return await self._enqueue_steering(event, event, binding, target_run_id, descriptor.id)

    async def _enqueue_steering(
        self,
        event: AgentEventEnvelope,
        execution_event: AgentEventEnvelope,
        binding: AgentBinding,
        target_run_id: str,
        runner_id: str,
    ) -> bool:
        steering_item = self._build_steering_item(execution_event, target_run_id, runner_id)
        # Reserve queue capacity without exposing an input before its source row exists.
        steering_item['_steering_pending'] = True
        if not await self._session_registry.enqueue_steering(target_run_id, steering_item):
            return False
        try:
            event_log_id = await self.journal.write_event_log(
                event=event,
                binding=binding,
                run_id=target_run_id,
                runner_id=runner_id,
                metadata={
                    'steering': {
                        'status': 'queued',
                        'trigger_behavior': 'absorbed_into_active_run',
                        'claimed_by_run_id': target_run_id,
                        'claimed_runner_id': runner_id,
                        'claimed_at': steering_item.get('claimed_at'),
                    }
                },
            )
            published = await self._session_registry.complete_steering_enqueue(
                target_run_id, event.event_id, persisted=True
            )
        except BaseException:
            await self._session_registry.complete_steering_enqueue(target_run_id, event.event_id, persisted=False)
            raise
        if not published:
            from .event_log_store import EventLogStore

            released = await EventLogStore(self.ap.persistence_mgr.get_db_engine()).update_steering_status(
                event.event_id, status='dropped', owner_run_id=target_run_id
            )
            if not released:
                raise RuntimeError(f'Cannot release steering event {event.event_id} after its run ended')
            return False
        try:
            await self.journal.write_user_transcript(event, event_log_id)
        except Exception as exc:
            self.ap.logger.warning(
                f'Failed to write steering transcript for event {event.event_id}: {exc}',
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
                # Refs address the claimed run's own input; a steering message's
                # media are described as metadata only.
                'attachments': [
                    {**(a.model_dump(mode='json') if hasattr(a, 'model_dump') else dict(a)), 'ref': None}
                    for a in (event.input.attachments if event.input else [])
                ],
            },
        }

    async def _load_recoverable_steering(
        self,
        *,
        event: AgentEventEnvelope,
        descriptor: RunnerDescriptor,
        run_id: str,
        binding: AgentBinding | None = None,
    ) -> list[dict[str, typing.Any]]:
        """Rebuild unacknowledged steering inputs after a run restart."""
        if not event.conversation_id or not descriptor.supports_steering():
            return []
        from .event_log_store import EventLogStore

        store = EventLogStore(self.ap.persistence_mgr.get_db_engine())
        records = await store.list_pending_steering(
            conversation_id=event.conversation_id,
            runner_id=descriptor.id,
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            thread_id=event.thread_id,
            binding_id=binding.binding_id if binding else None,
        )
        recovered: list[dict[str, typing.Any]] = []
        for record in records:
            source_run_id = record.get('run_id')
            if source_run_id == run_id:
                continue
            if source_run_id and await self._session_registry.get(str(source_run_id)) is not None:
                continue
            if not await store.reserve_steering_recovery(str(record['event_id']), run_id=run_id):
                continue
            metadata = record.get('metadata') if isinstance(record.get('metadata'), dict) else {}
            steering = metadata.get('steering') if isinstance(metadata.get('steering'), dict) else {}
            input_json = record.get('input_json') if isinstance(record.get('input_json'), dict) else {}
            event_data = metadata.get('input_event') if isinstance(metadata.get('input_event'), dict) else {}
            item: dict[str, typing.Any] = {
                'claimed_run_id': run_id,
                'runner_id': descriptor.id,
                'claimed_at': record.get('created_at') or int(time.time()),
                'event': {
                    'event_id': record.get('event_id'),
                    'event_type': record.get('event_type'),
                    'event_time': record.get('event_time'),
                    'source': record.get('source'),
                    'data': event_data,
                },
                'conversation': {
                    'conversation_id': record.get('conversation_id'),
                    'thread_id': record.get('thread_id'),
                    'bot_id': record.get('bot_id'),
                    'workspace_id': record.get('workspace_id'),
                },
                'actor': (
                    {
                        'actor_type': record.get('actor_type'),
                        'actor_id': record.get('actor_id'),
                        'actor_name': record.get('actor_name'),
                    }
                    if record.get('actor_type')
                    else None
                ),
                'subject': (
                    {
                        'subject_type': record.get('subject_type'),
                        'subject_id': record.get('subject_id'),
                    }
                    if record.get('subject_type')
                    else None
                ),
                'input': {
                    'text': input_json.get('text'),
                    'contents': input_json.get('contents') or [],
                    'attachments': input_json.get('attachments') or [],
                },
                'metadata': {'recovered': True, 'source_run_id': source_run_id},
            }
            delivery_id = steering.get('delivery_id')
            lease_expires_at = steering.get('lease_expires_at')
            if delivery_id:
                item['_steering_delivery_id'] = delivery_id
            if isinstance(lease_expires_at, int):
                item['_steering_lease_expires_at'] = lease_expires_at
            recovered.append(item)
        return recovered

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

    async def _finalize_run(self, **kwargs: typing.Any) -> dict[str, typing.Any] | None:
        """Write this execution's terminal status unless the run already has one.

        Another writer can finish the run first: the Runner finalizing its own
        run, a cancel request, or lease recovery marking it interrupted. The
        first terminal status stays; closing the stream afterwards must not
        raise, which would replace the real outcome (or a pending
        cancellation) with a second, unrelated failure.
        """
        try:
            return await self.journal.finalize_run(**kwargs)
        except TerminalRunTransitionError as exc:
            self.ap.logger.info(f'Run already finalized, keeping its terminal status: {exc}')
            return await self.journal.get_run(kwargs['run_id'])

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
