"""Dispatch explicit retry/resume requests through the normal Host Runner path."""

from __future__ import annotations

import asyncio
import contextlib
import json
from uuid import uuid4

from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events

from ...api.http.context import ExecutionContext
from ...pipeline.extension_preferences import normalize_extension_preferences
from .config_resolver import RunnerConfigResolver
from .config_schema import extract_prompt_config, uses_host_tools
from .execution_context import build_execution_query, project_mcp_resource_config
from .host_models import AgentEventEnvelope
from .query_entry_adapter import QueryEntryAdapter
from .run_ledger_store import RunLedgerStore, TERMINAL_STATUSES
from .resource_policy import ResourcePolicyProjector


class _RecoveryDeliveryAdapter:
    """Keep Pipeline output stages while replying from the durable event target."""

    def __init__(self, adapter, event, *, quote_origin):
        self._adapter = adapter
        self._target = event.delivery.reply_target or {}
        if not self._target.get('target_type') or not self._target.get('target_id'):
            raise ValueError('Recovery input has no complete reply target')
        self._context = {
            'event_type': event.event_type,
            'data': event.data,
            'delivery': event.delivery.model_dump(mode='json'),
            'quote_origin': quote_origin,
        }
        if quote_origin and (
            not self._target.get('message_id')
            or not (
                callable(getattr(adapter, 'reply_to_event', None)) or callable(getattr(adapter, 'get_message', None))
            )
        ):
            raise ValueError('This platform cannot restore the original message for a quoted Pipeline reply')

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    async def is_stream_output_supported(self):
        return False

    async def reply_message(self, message_source, message, quote_origin=False):
        target_type, target_id = self._target['target_type'], self._target['target_id']
        reply_to_event = getattr(self._adapter, 'reply_to_event', None)
        if callable(reply_to_event):
            return await reply_to_event(
                context={**self._context, 'quote_origin': quote_origin},
                target_type=target_type,
                target_id=target_id,
                message=message,
            )
        if quote_origin:
            source = await self._adapter.get_message(
                chat_type=target_type,
                chat_id=target_id,
                message_id=self._target['message_id'],
            )
            return await self._adapter.reply_message(source, message, quote_origin=True)
        return await self._adapter.send_message(target_type, target_id, message)


def _has_redacted_content(value):
    if isinstance(value, dict):
        return value.get('content_redacted') is True or any(_has_redacted_content(v) for v in value.values())
    return isinstance(value, list) and any(_has_redacted_content(v) for v in value)


async def _resume_events(store, source_run_id, from_sequence):
    authorization = await store.get_run_authorization(source_run_id)
    inherited = authorization.get('recovery_checkpoint', [])
    events = []
    cursor = None
    while True:
        page, cursor, _, more = await store.page_run_events(run_id=source_run_id, after_sequence=cursor, limit=100)
        events.extend(item for item in page if item['source'] == 'runner')
        if len(events) > 1000 or len(json.dumps(events).encode()) > 1024 * 1024:
            raise ValueError('Resume checkpoint exceeds the bounded context; retry explicitly instead')
        if not more:
            break
    last_sequence = events[-1]['sequence'] if events else 0
    if from_sequence is not None and from_sequence != last_sequence:
        raise ValueError(
            f'Resume requires the latest committed Runner sequence ({last_sequence}); rewinding is not supported'
        )
    events = inherited + events
    if len(events) > 1000 or len(json.dumps(events).encode()) > 1024 * 1024:
        raise ValueError('Resume checkpoint exceeds the bounded context; retry explicitly instead')
    outstanding = set()
    for event in events:
        data = event['data']
        if event['type'] == 'tool.call.started':
            outstanding.add(data.get('tool_call_id'))
        elif event['type'] == 'tool.call.completed':
            outstanding.discard(data.get('tool_call_id'))
    if outstanding:
        raise ValueError('A tool has no committed completion; inspect its effects before retrying')
    return events, last_sequence


async def dispatch_recovery(ap, source, *, resume=False, from_sequence=None, reason=None):
    """Return the new execution; leave the source attempt and its results intact."""
    if source['status'] not in TERMINAL_STATUSES:
        raise ValueError('Only terminal runs can be retried or resumed')
    if resume and source['status'] == 'completed':
        raise ValueError('A completed run has no interrupted work to resume')
    store = RunLedgerStore(ap.persistence_mgr.get_db_engine())
    authorization = await store.get_run_authorization(source['run_id'])
    snapshot = authorization.get('recovery_event')
    if not isinstance(snapshot, dict) or _has_redacted_content(snapshot):
        raise ValueError('This run has no complete durable input; submit the original input again')
    event = AgentEventEnvelope.model_validate(snapshot)
    if event.workspace_id != source['workspace_id'] or event.bot_id != source['bot_id']:
        raise ValueError('Recovery input does not match the recorded execution scope')
    placement = await ap.workspace_service.get_execution_binding(source['workspace_id'])
    context = ExecutionContext(
        instance_uuid=placement.instance_uuid,
        workspace_uuid=placement.workspace_uuid,
        placement_generation=placement.placement_generation,
        bot_uuid=source['bot_id'],
        pipeline_uuid=authorization.get('processor_id') if authorization.get('processor_type') == 'pipeline' else None,
    )
    processor_id = source.get('agent_id') or authorization.get('processor_id')
    if not processor_id:
        raise ValueError('Run has no processor to dispatch')
    orchestrator = ap.agent_run_orchestrator
    bound_plugins = None
    if authorization.get('processor_type') == 'pipeline':
        pipeline = await ap.pipeline_service.get_pipeline(context, processor_id, include_secret=True)
        if not pipeline:
            raise ValueError('Pipeline is no longer available in this Workspace')
        query = build_execution_query(event, [], context)
        query.pipeline_config = pipeline['config']
        query.pipeline_uuid = processor_id
        prefs = normalize_extension_preferences(pipeline.get('extensions_preferences', {}))
        bound_plugins = (
            None if prefs['enable_all_plugins'] else [f'{p["author"]}/{p["name"]}' for p in prefs['plugins']]
        )
        query.variables['_pipeline_bound_plugins'] = bound_plugins
        query.variables['_pipeline_bound_mcp_servers'] = (
            None if prefs['enable_all_mcp_servers'] else prefs['mcp_servers']
        )
        query.variables['_pipeline_bound_skills'] = None if prefs['enable_all_skills'] else prefs['skills']
        query.variables['_pipeline_workspace_operations'] = prefs['workspace_operations']
        query.variables['_pipeline_allowed_platform_tools'] = prefs['allowed_platform_tools']
        runner_id = RunnerConfigResolver.resolve_runner_id(pipeline['config'])
        runner_config = RunnerConfigResolver.resolve_runner_config(pipeline['config'], runner_id)
        descriptor = await orchestrator.registry.get(context, runner_id, bound_plugins)
        query.variables['_pipeline_mcp_resource_attachments'] = runner_config.get(
            'mcp-resources', prefs['mcp_resources']
        )
        query.variables['_pipeline_mcp_resource_agent_read_enabled'] = runner_config.get(
            'mcp-resource-agent-read-enabled', prefs['mcp_resource_agent_read_enabled']
        )
        if uses_host_tools(descriptor):
            from ...provider.tools.toolmgr import ToolManager

            catalog = await ap.tool_mgr.get_resolved_tool_catalog(
                context,
                bound_plugins,
                query.variables['_pipeline_bound_mcp_servers'],
                include_skill_authoring=True,
                include_mcp_resource_tools=query.variables['_pipeline_mcp_resource_agent_read_enabled'],
            )
            policy = ResourcePolicyProjector.from_runner_config(
                runner_config, resolved_tool_names=ResourcePolicyProjector.extract_tool_names(catalog)
            )
            catalog = ResourcePolicyProjector.filter_tools(catalog, policy)
            ToolManager.bind_query_tool_sources(query, catalog)
            query.use_funcs = ToolManager.tools_from_catalog(catalog)
        binding = orchestrator.binding_resolver.resolve_one(
            event, [QueryEntryAdapter.config_to_agent_config(query, runner_id)]
        )
    else:
        agent = await ap.agent_service.get_agent(context, processor_id)
        if not agent or agent.get('kind') != authorization.get('processor_type'):
            raise ValueError('Processor is no longer available in this Workspace')
        from ...platform.botmgr import RuntimeBot

        binding = RuntimeBot._agent_product_to_binding(agent, {}, event.event_type, event.bot_id)
        query = None
    if binding is None or binding.runner_id != source['runner_id']:
        raise ValueError('Processor Runner has changed; submit a new request')
    binding.binding_id = source['binding_id']
    descriptor = await orchestrator.registry.get(context, binding.runner_id, bound_plugins)
    if query is not None:
        from langbot_plugin.api.entities.builtin.provider.prompt import Prompt
        from langbot_plugin.api.entities.builtin.provider.message import Message

        query.prompt = Prompt(
            name='default',
            messages=[Message(**item) for item in extract_prompt_config(descriptor, binding.runner_config, [])],
        )
        project_mcp_resource_config(query, binding.runner_config)
    if resume and descriptor.raw_manifest.get('metadata', {}).get('supports_resume') is not True:
        raise ValueError('This Runner does not support checkpoint resume')
    events, sequence = await _resume_events(store, source['run_id'], from_sequence) if resume else ([], None)
    request = {
        'mode': 'resume' if resume else 'retry',
        'source_run_id': source['run_id'],
        'from_sequence': sequence,
        'events': events,
        'reason': reason,
    }
    adapter = None
    if event.delivery.surface == 'platform' and event.delivery.reply_target:
        bot = await ap.bot_mgr.get_bot_by_uuid(context, event.bot_id)
        if bot is None:
            raise ValueError('The original delivery bot is no longer available')
        adapter = bot.adapter
    output_pipeline = None
    if query is not None and adapter is not None:
        output_pipeline = await ap.pipeline_mgr.prepare_pipeline(context, pipeline)
        query.adapter = _RecoveryDeliveryAdapter(
            adapter, event, quote_origin=query.pipeline_config['output']['misc']['quote-origin']
        )
        query.resp_message_chain = []
        query.message_event = platform_events.MessageReceivedEvent(
            timestamp=query.message_event.time or 0.0,
            message_id=str(event.delivery.reply_target.get('message_id') or ''),
            message_chain=query.message_chain,
            sender=platform_entities.User(id=query.sender_id),
            chat_type='group' if query.launcher_type.value == 'group' else 'private',
            chat_id=query.launcher_id,
        ).to_legacy_event()
        # Recovered Pipeline output follows its normal filters/wrapper/sender,
        # never the Agent-only direct reply shortcut.
        event.delivery.supports_streaming = False
    run_id = str(uuid4())
    event = event.model_copy(update={'event_id': f'recovery:{run_id}'}, deep=True)
    record, created = await store.create_recovery_run(
        source_run_id=source['run_id'],
        run_id=run_id,
        event_id=event.event_id,
        metadata={
            'processor_type': binding.processor_type,
            'processor_id': processor_id,
            'recovery': {key: value for key, value in request.items() if key != 'events'},
        },
    )
    if not created:
        return record

    async def execute():
        tenant_scope = getattr(ap.persistence_mgr, 'tenant_scope', None)
        async with tenant_scope(context.workspace_uuid) if tenant_scope else contextlib.nullcontext():
            await execute_in_scope()

    async def execute_in_scope():
        try:
            await ap.workspace_service.get_execution_binding(
                context.workspace_uuid, expected_generation=context.placement_generation
            )
            adapter_context = {
                '_execution_context': context,
                '_delivery_adapter': adapter,
                '_recovery': {'run_id': run_id, 'request': request},
            }
            if query is not None:
                adapter_context['_query'] = query
                if output_pipeline is not None:
                    adapter_context['_recovery_delivery_adapter'] = query.adapter
            async with contextlib.aclosing(orchestrator.run(event, binding, bound_plugins, adapter_context)) as results:
                async for result in results:
                    from langbot_plugin.api.entities.builtin.provider.message import Message

                    if output_pipeline is not None and isinstance(result, Message):
                        await output_pipeline.deliver_runner_result(query, result)
        except BaseException as exc:
            latest = await store.get_run(run_id)
            if latest and latest['status'] not in TERMINAL_STATUSES:
                await store.finalize_run(
                    run_id=run_id,
                    status='cancelled' if isinstance(exc, asyncio.CancelledError) else 'failed',
                    status_reason=str(exc) or type(exc).__name__,
                )
            raise

    try:
        ap.task_mgr.create_user_task(
            execute(),
            kind='runner-recovery',
            name=run_id,
            instance_uuid=context.instance_uuid,
            workspace_uuid=context.workspace_uuid,
            placement_generation=context.placement_generation,
        )
    except Exception as exc:
        await store.finalize_run(run_id=run_id, status='failed', status_reason=str(exc))
        raise
    return record
